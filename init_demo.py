"""Initialize a fresh, disposable demo DB; credentials come from environment."""
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app import connect, init_db, now, TZ

def seed_demo():
    username = os.environ.get('DEMO_ADMIN_USER', 'admin').strip()
    password = os.environ.get('DEMO_ADMIN_PASSWORD', '')
    if len(username) < 3 or len(password) < 12:
        raise RuntimeError('Set DEMO_ADMIN_USER (>=3 chars) and DEMO_ADMIN_PASSWORD (>=12 chars)')
    init_db()
    with connect() as db:
        if not db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',
                       (username, generate_password_hash(password), 'admin'))
        if db.execute('SELECT 1 FROM products LIMIT 1').fetchone():
            return
        demo = [('MB-001','Main Board 55 inch','Electronics',22,5),
                ('PS-002','Power Supply Board','Electronics',14,5),
                ('LED-003','LED Backlight Strip','Lighting',3,8),
                ('CAB-004','HDMI Cable','Cables',48,10),
                ('REM-005','Remote Control','Accessories',7,10),
                ('SPK-006','Speaker Set','Audio',19,6),
                ('CON-007','Connector Kit','Cables',36,10),
                ('PNL-008','Display Panel','Display',4,5)]
        for sku,name,cat,qty,minimum in demo:
            cur=db.execute('INSERT INTO products(sku,name,category,quantity,minimum,created_at) VALUES(?,?,?,?,?,?)',
                           (sku,name,cat,qty,minimum,now()))
            # Keep demo inventory and movement totals consistent.
            for days,kind,q in [(12,'IN',qty+9),(5,'OUT',9)]:
                db.execute('INSERT INTO movements(product_id,kind,qty,actor,note,created_at) VALUES(?,?,?,?,?,?)',
                           (cur.lastrowid,kind,q,username,'Demo sample',
                            (datetime.now(TZ)-timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')))

if __name__ == '__main__':
    seed_demo()
    print('Demo database initialized (credentials not printed).')
