import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ['STOCK_DB_PATH']=os.path.join(self.tmp.name,'test.db')
        import app
        app.DB=os.environ['STOCK_DB_PATH']
        app.app.config['TESTING']=True
        app.init_db()
        with app.connect() as db:
            db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',('admin',app.generate_password_hash('StrongPassword123!'),'admin'))
            db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',('staff',app.generate_password_hash('StrongPassword123!'),'staff'))
        self.mod=app; self.client=app.app.test_client()
    def tearDown(self): self.tmp.cleanup()
    def login(self,user='admin'):
        self.client.post('/login',data={'username':user,'password':'StrongPassword123!'})
        with self.client.session_transaction() as s: return s['csrf']
    def test_auth_and_dashboard(self):
        self.assertEqual(self.client.get('/').status_code,302)
        self.login(); self.assertEqual(self.client.get('/').status_code,200)
    def test_product_and_stock(self):
        csrf=self.login()
        self.client.post('/products',data={'_csrf':csrf,'sku':'ABC','name':'Test','minimum':'5'})
        with self.mod.connect() as db: pid=db.execute('SELECT id FROM products WHERE sku=?',('ABC',)).fetchone()[0]
        self.client.post('/movements',data={'_csrf':csrf,'product_id':pid,'kind':'IN','qty':7})
        self.client.post('/movements',data={'_csrf':csrf,'product_id':pid,'kind':'OUT','qty':8})
        with self.mod.connect() as db: self.assertEqual(db.execute('SELECT quantity FROM products WHERE id=?',(pid,)).fetchone()[0],7)
        self.assertEqual(self.client.get('/analytics').status_code,200)
        self.assertEqual(self.client.get('/reports/export.csv').status_code,200)
    def test_staff_forbidden(self):
        csrf=self.login('staff')
        self.assertEqual(self.client.get('/users').status_code,403)
        self.assertEqual(self.client.post('/products',data={'_csrf':csrf,'sku':'X','name':'Y','minimum':5}).status_code,403)
    def test_csrf(self):
        self.login(); self.assertEqual(self.client.post('/products',data={'sku':'X','name':'Y'}).status_code,403)

if __name__=='__main__': unittest.main()
