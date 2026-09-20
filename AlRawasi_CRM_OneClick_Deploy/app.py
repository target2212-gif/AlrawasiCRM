from flask import Flask,request,redirect,url_for,render_template,session,flash,jsonify
import hashlib
def check_password_hash(stored,pw):
 try:
  salt,hexd=stored.split('$',1); return hashlib.pbkdf2_hmac('sha256',pw.encode(),salt.encode(),200000).hex()==hexd
 except: return False
def generate_password_hash(pw):
 import secrets; salt=secrets.token_hex(16); return salt+'$'+hashlib.pbkdf2_hmac('sha256',pw.encode(),salt.encode(),200000).hex()
import sqlite3, os, json, urllib.parse
from functools import wraps
from datetime import datetime
app=Flask(__name__); app.secret_key=os.environ.get('SECRET_KEY','change-this-secret')
DB=os.path.join(os.path.dirname(__file__),'crm.db')
STATUS={'new':'جديد','contacted':'تم التواصل','interested':'مهتم','quote_requested':'طلب عرض سعر','quote_sent':'تم إرسال عرض السعر','followup':'متابعة','contracted':'تم التعاقد','not_interested':'غير مهتم','unreachable':'لا يمكن التواصل','postponed':'مؤجل'}
def db(): x=sqlite3.connect(DB); x.row_factory=sqlite3.Row; return x
def login_required(f):
 @wraps(f)
 def w(*a,**k):
  if 'uid' not in session:return redirect(url_for('login'))
  return f(*a,**k)
 return w
@app.context_processor
def ctx(): return {'status':STATUS,'user':session.get('name')}
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  d=db(); u=d.execute('SELECT * FROM users WHERE email=? AND active=1',(request.form['email'],)).fetchone(); d.close()
  if u and check_password_hash(u['password_hash'],request.form['password']): session.update(uid=u['id'],name=u['name'],role=u['role']); return redirect(url_for('dashboard'))
  flash('بيانات الدخول غير صحيحة')
 return render_template('login.html')
@app.get('/health')
def health(): return jsonify({'status':'ok'})
@app.get('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.get('/')
@login_required
def dashboard():
 d=db(); counts={k:d.execute('SELECT COUNT(*) n FROM companies WHERE marketing_status=?',(k,)).fetchone()['n'] for k in STATUS}; total=d.execute('SELECT COUNT(*) n FROM companies').fetchone()['n']; follow=d.execute("SELECT COUNT(*) n FROM interactions WHERE next_followup_at IS NOT NULL AND date(next_followup_at)<=date('now')").fetchone()['n']; reps=d.execute("SELECT u.name,COUNT(c.id) n FROM users u LEFT JOIN companies c ON c.assigned_user_id=u.id GROUP BY u.id ORDER BY n DESC").fetchall(); d.close(); return render_template('dashboard.html',counts=counts,total=total,follow=follow,reps=reps)
@app.get('/companies')
@login_required
def companies():
 q=request.args.get('q','').strip(); city=request.args.get('city','').strip(); status=request.args.get('status','').strip(); page=max(1,int(request.args.get('page',1))); per=50; where=[]; args=[]
 if q: where.append('(name_ar LIKE ? OR name_en LIKE ? OR phone_mobile LIKE ? OR phone_landline LIKE ? OR email LIKE ?)'); args += [f'%{q}%']*5
 if city: where.append('city=?'); args.append(city)
 if status: where.append('marketing_status=?'); args.append(status)
 w=(' WHERE '+' AND '.join(where)) if where else ''
 d=db(); total=d.execute('SELECT COUNT(*) n FROM companies'+w,args).fetchone()['n']; rows=d.execute('SELECT c.*,u.name rep FROM companies c LEFT JOIN users u ON u.id=c.assigned_user_id'+w+' ORDER BY c.id LIMIT ? OFFSET ?',args+[per,(page-1)*per]).fetchall(); cities=d.execute("SELECT DISTINCT city FROM companies WHERE city IS NOT NULL AND city<>'' ORDER BY city").fetchall(); d.close(); return render_template('companies.html',rows=rows,total=total,page=page,per=per,q=q,city=city,status_filter=status,cities=cities)
@app.get('/company/<int:cid>')
@login_required
def company(cid):
 d=db(); c=d.execute('SELECT c.*,u.name rep FROM companies c LEFT JOIN users u ON u.id=c.assigned_user_id WHERE c.id=?',(cid,)).fetchone(); its=d.execute('SELECT i.*,u.name rep FROM interactions i LEFT JOIN users u ON u.id=i.user_id WHERE company_id=? ORDER BY contacted_at DESC',(cid,)).fetchall(); users=d.execute('SELECT * FROM users WHERE active=1').fetchall(); temps=d.execute('SELECT * FROM templates ORDER BY id').fetchall(); d.close(); return render_template('company.html',c=c,its=its,users=users,temps=temps)
@app.post('/company/<int:cid>/update')
@login_required
def update_company(cid):
 d=db(); d.execute('UPDATE companies SET marketing_status=?,assigned_user_id=?,priority=?,marketing_notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(request.form['marketing_status'],request.form.get('assigned_user_id') or None,request.form.get('priority','normal'),request.form.get('marketing_notes',''),cid)); d.commit(); d.close(); return redirect(url_for('company',cid=cid))
@app.post('/company/<int:cid>/interaction')
@login_required
def interaction(cid):
 d=db(); d.execute('INSERT INTO interactions(company_id,user_id,channel,outcome,notes,next_followup_at) VALUES(?,?,?,?,?,?)',(cid,session['uid'],request.form['channel'],request.form['outcome'],request.form.get('notes',''),request.form.get('next_followup_at') or None)); d.execute('UPDATE companies SET marketing_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(request.form['outcome'],cid)); d.commit(); d.close(); return redirect(url_for('company',cid=cid))
@app.get('/users')
@login_required
def users():
 if session.get('role')!='admin': return redirect(url_for('dashboard'))
 d=db(); rows=d.execute('SELECT id,name,email,role,active FROM users ORDER BY id').fetchall(); d.close(); return render_template('users.html',rows=rows)
@app.post('/users/add')
@login_required
def add_user():
 if session.get('role')!='admin': return redirect(url_for('dashboard'))
 d=db(); d.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',(request.form['name'],request.form['email'],generate_password_hash(request.form['password']),request.form['role'])); d.commit(); d.close(); return redirect(url_for('users'))
@app.get('/export')
@login_required
def export():
 import csv,io
 d=db(); rows=d.execute('SELECT * FROM companies ORDER BY id').fetchall(); out=io.StringIO(); w=csv.writer(out); w.writerow(rows[0].keys() if rows else ['id']); [w.writerow(list(r)) for r in rows]; d.close(); from flask import Response; return Response('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=companies.csv'})
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
