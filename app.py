import os, sqlite3, csv, io, secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, Response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY') or secrets.token_hex(32)
if os.getenv('RENDER') and not os.getenv('FLASK_SECRET_KEY'):
    raise RuntimeError('Set FLASK_SECRET_KEY in Render environment variables')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('RENDER') is not None or os.getenv('COOKIE_SECURE','0')=='1')
DB = os.getenv('STOCK_DB_PATH', os.path.join(BASE, 'stock.db'))
TZ = timezone(timedelta(hours=7))

def now(): return datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
def connect():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=10000')
    return conn

def init_db():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','staff')));
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, sku TEXT UNIQUE NOT NULL, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'General', unit TEXT NOT NULL DEFAULT 'pcs', quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity>=0), minimum INTEGER NOT NULL DEFAULT 5 CHECK(minimum>=0), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), kind TEXT NOT NULL CHECK(kind IN ('IN','OUT')), qty INTEGER NOT NULL CHECK(qty>0), actor TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_movements_date ON movements(created_at);
        CREATE INDEX IF NOT EXISTS idx_movements_product ON movements(product_id);
        ''')

@app.before_request
def prepare():
    if request.endpoint == 'static': return
    init_db()
    if request.method == 'POST' and request.endpoint not in ('login',):
        if not session.get('uid') or request.form.get('_csrf') != session.get('csrf'):
            abort(403)

@app.context_processor
def context():
    return {'me': session.get('username'), 'role':session.get('role'), 'csrf':session.get('csrf',''), 'year':datetime.now().year}

def login_required(fn):
    @wraps(fn)
    def wrapped(*a,**kw):
        if not session.get('uid'): return redirect(url_for('login'))
        return fn(*a,**kw)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*a,**kw):
        if session.get('role')!='admin': abort(403)
        return fn(*a,**kw)
    return wrapped

@app.route('/setup',methods=['GET','POST'])
def setup():
    if os.getenv('RENDER'): abort(404)
    with connect() as db:
        count=db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if count: return redirect(url_for('login'))
    if request.method=='POST':
        u=request.form.get('username','').strip()
        p=request.form.get('password','')
        if len(u)<3 or len(p)<12:
            flash('Username อย่างน้อย 3 ตัว และ Password อย่างน้อย 12 ตัว','error')
        else:
            with connect() as db:
                try: db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(u,generate_password_hash(p),'admin'))
                except sqlite3.IntegrityError: flash('มีบัญชีนี้แล้ว','error')
                else:
                    flash('สร้าง Admin สำเร็จ กรุณาเข้าสู่ระบบ','success')
                    return redirect(url_for('login'))
    return render_template('setup.html')

@app.route('/login',methods=['GET','POST'])
def login():
    with connect() as db:
        if not db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            if os.getenv('RENDER'): abort(503)
            return redirect(url_for('setup'))
    if request.method=='POST':
        with connect() as db: user=db.execute('SELECT * FROM users WHERE username=?',(request.form.get('username',''),)).fetchone()
        if user and check_password_hash(user['password_hash'],request.form.get('password','')):
            session.clear(); session.update(uid=user['id'],username=user['username'],role=user['role'],csrf=secrets.token_urlsafe(32))
            return redirect(url_for('dashboard'))
        flash('Username หรือ Password ไม่ถูกต้อง','error')
    return render_template('login.html')

@app.post('/logout')
@login_required
def logout():
    session.clear(); return redirect(url_for('login'))

@app.get('/')
@login_required
def dashboard():
    with connect() as db:
        products=db.execute('SELECT * FROM products ORDER BY name').fetchall()
        low=[p for p in products if p['quantity']<=p['minimum']]
        recent=db.execute('''SELECT m.*,p.sku,p.name FROM movements m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT 7''').fetchall()
        inbound=db.execute("SELECT COALESCE(SUM(qty),0) FROM movements WHERE kind='IN'").fetchone()[0]
        outbound=db.execute("SELECT COALESCE(SUM(qty),0) FROM movements WHERE kind='OUT'").fetchone()[0]
    return render_template('dashboard.html',active='dashboard',products=products,low=low,recent=recent,inbound=inbound,outbound=outbound,charts=analytics_data())

@app.get('/inventory')
@login_required
def inventory():
    q=request.args.get('q','').strip()
    with connect() as db:
        products=db.execute('SELECT * FROM products WHERE sku LIKE ? OR name LIKE ? OR category LIKE ? ORDER BY name',tuple('%'+q+'%' for _ in range(3))).fetchall()
    return render_template('inventory.html',active='inventory',products=products,q=q)

@app.post('/products')
@admin_required
def add_product():
    sku=request.form.get('sku','').strip().upper(); name=request.form.get('name','').strip()
    try: minimum=int(request.form.get('minimum','5'))
    except ValueError: minimum=-1
    if not sku or not name or minimum<0: flash('กรอกข้อมูลสินค้าให้ถูกต้อง','error')
    else:
        try:
            with connect() as db: db.execute('INSERT INTO products(sku,name,category,unit,minimum,created_at) VALUES(?,?,?,?,?,?)',(sku,name,request.form.get('category','General').strip() or 'General',request.form.get('unit','pcs').strip() or 'pcs',minimum,now()))
            flash('เพิ่มสินค้าสำเร็จ','success')
        except sqlite3.IntegrityError: flash('SKU นี้มีอยู่แล้ว','error')
    return redirect(url_for('inventory'))

@app.post('/products/<int:pid>/edit')
@admin_required
def edit_product(pid):
    try: minimum=int(request.form.get('minimum','5'))
    except ValueError: minimum=-1
    name=request.form.get('name','').strip()
    if not name or minimum<0: flash('ข้อมูลไม่ถูกต้อง','error')
    else:
        with connect() as db: db.execute('UPDATE products SET name=?,category=?,unit=?,minimum=? WHERE id=?',(name,request.form.get('category','General').strip() or 'General',request.form.get('unit','pcs').strip() or 'pcs',minimum,pid))
        flash('บันทึกการแก้ไขแล้ว','success')
    return redirect(url_for('inventory'))

@app.route('/movements',methods=['GET','POST'])
@login_required
def movements():
    if request.method=='POST':
        try: pid=int(request.form.get('product_id','')); qty=int(request.form.get('qty',''))
        except ValueError: pid=0; qty=0
        kind=request.form.get('kind','')
        if qty<=0 or kind not in ('IN','OUT'):
            flash('จำนวนและประเภทรายการไม่ถูกต้อง','error')
        else:
            with connect() as db:
                product=db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
                if not product: flash('ไม่พบสินค้า','error')
                elif kind=='OUT' and product['quantity']<qty: flash('สต็อกไม่เพียงพอ','error')
                else:
                    change=qty if kind=='IN' else -qty
                    cur=db.execute('UPDATE products SET quantity=quantity+? WHERE id=? AND quantity+?>=0',(change,pid,change))
                    if cur.rowcount:
                        db.execute('INSERT INTO movements(product_id,kind,qty,actor,note,created_at) VALUES(?,?,?,?,?,?)',(pid,kind,qty,session['username'],request.form.get('note','').strip()[:300],now()))
                        flash('บันทึกรายการเรียบร้อย','success')
                    else: flash('สต็อกไม่เพียงพอ','error')
        return redirect(url_for('movements'))
    with connect() as db:
        products=db.execute('SELECT * FROM products ORDER BY name').fetchall()
        history=db.execute('SELECT m.*,p.sku,p.name FROM movements m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT 100').fetchall()
    return render_template('movements.html',active='movements',products=products,history=history)

def analytics_data():
    with connect() as db:
        daily=db.execute("SELECT substr(created_at,1,10) AS day,kind,SUM(qty) AS total FROM movements WHERE created_at >= ? GROUP BY day,kind",((datetime.now(TZ)-timedelta(days=13)).strftime('%Y-%m-%d'),)).fetchall()
        top=db.execute("SELECT p.name,SUM(m.qty) AS qty FROM movements m JOIN products p ON p.id=m.product_id WHERE m.kind='OUT' GROUP BY p.id ORDER BY qty DESC LIMIT 6").fetchall()
        cats=db.execute('SELECT category,SUM(quantity) AS qty FROM products GROUP BY category ORDER BY qty DESC').fetchall()
    dates=[(datetime.now(TZ)-timedelta(days=i)).strftime('%Y-%m-%d') for i in range(13,-1,-1)]
    index={(r['day'],r['kind']):r['total'] for r in daily}
    return dict(dates=dates,received=[index.get((d,'IN'),0) for d in dates],issued=[index.get((d,'OUT'),0) for d in dates],top_labels=[r['name'] for r in top],top_values=[r['qty'] for r in top],category_labels=[r['category'] for r in cats],category_values=[r['qty'] for r in cats])

@app.get('/analytics')
@login_required
def analytics(): return render_template('analytics.html',active='analytics',charts=analytics_data())

@app.get('/reports')
@login_required
def reports():
    with connect() as db: rows=db.execute('SELECT m.*,p.sku,p.name FROM movements m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT 500').fetchall()
    return render_template('reports.html',active='reports',rows=rows)

@app.get('/reports/export.csv')
@login_required
def export():
    with connect() as db: rows=db.execute('SELECT m.created_at,p.sku,p.name,m.kind,m.qty,m.actor,m.note FROM movements m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC').fetchall()
    buf=io.StringIO(); w=csv.writer(buf); w.writerow(['Date (Asia/Bangkok)','SKU','Product','Type','Quantity','User','Note']); w.writerows([list(r) for r in rows]); return Response('\ufeff'+buf.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=stock-movements.csv'})

@app.route('/users',methods=['GET','POST'])
@admin_required
def users():
    if request.method=='POST':
        username=request.form.get('username','').strip(); password=request.form.get('password',''); role=request.form.get('role','staff')
        if len(username)<3 or len(password)<12 or role not in ('admin','staff'): flash('กรอกข้อมูลให้ถูกต้อง (รหัสผ่านอย่างน้อย 12 ตัว)','error')
        else:
            try:
                with connect() as db: db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(username,generate_password_hash(password),role))
                flash('สร้างบัญชีสำเร็จ','success')
            except sqlite3.IntegrityError: flash('ชื่อผู้ใช้ซ้ำ','error')
        return redirect(url_for('users'))
    with connect() as db: people=db.execute('SELECT id,username,role FROM users ORDER BY id').fetchall()
    return render_template('users.html',active='users',people=people)

@app.errorhandler(403)
def forbidden(e): return render_template('error.html',code=403,message='ไม่มีสิทธิ์ดำเนินการ'),403

if __name__=='__main__':
    import sys
    init_db()
    if '--seed-demo' in sys.argv:
        from init_demo import seed_demo
        seed_demo()
    else: app.run(host='127.0.0.1',port=int(os.getenv('PORT','5050')),debug=False)
