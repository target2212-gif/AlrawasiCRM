from flask import Flask,request,redirect,url_for,render_template,session,flash,jsonify,abort,Response
import hashlib, sqlite3, os, urllib.parse, csv, io
from functools import wraps

def check_password_hash(stored,pw):
 try:
  salt,hexd=stored.split('$',1); return hashlib.pbkdf2_hmac('sha256',pw.encode(),salt.encode(),200000).hex()==hexd
 except: return False
def generate_password_hash(pw):
 import secrets; salt=secrets.token_hex(16); return salt+'$'+hashlib.pbkdf2_hmac('sha256',pw.encode(),salt.encode(),200000).hex()

app=Flask(__name__); app.secret_key=os.environ.get('SECRET_KEY','change-this-secret')
DB=os.path.join(os.path.dirname(__file__),'crm.db')
STATUS={'new':'جديد','contacted':'تم التواصل','interested':'مهتم','quote_requested':'طلب عرض سعر','quote_sent':'تم إرسال عرض السعر','followup':'متابعة','contracted':'تم التعاقد','not_interested':'غير مهتم','unreachable':'لا يمكن التواصل','postponed':'مؤجل'}
STATUS_CLASS={k:'status-'+k.replace('_','-') for k in STATUS}
SPECIALTIES={'contracting':'خدمات المقاولين والشهادات','advertising':'الدعاية والإعلان','general':'خدمات عامة'}
DEFAULT_MESSAGES={
 'contracting':'السلام عليكم، معك {rep_name} من تلال الرواسي. نقدم خدمات تصنيف شركات المقاولات، شهادة المحتوى المحلي، وشهادات الأيزو. يسعدنا خدمة {company_name} وتزويدكم بالتفاصيل والعرض المناسب.',
 'advertising':'السلام عليكم، معك {rep_name} من تلال الرواسي للدعاية والإعلان. نقدم لوحات المحلات التجارية، الاستيكرات، البنرات، بوثات المعارض، الهوية والمطبوعات. يسعدنا خدمة {company_name} وتقديم عرض مناسب لاحتياجكم.',
 'general':'السلام عليكم، معك {rep_name} من تلال الرواسي. يسعدنا التعرف على احتياج {company_name} وتقديم خدماتنا والحلول المناسبة لكم.'}

def db(): x=sqlite3.connect(DB); x.row_factory=sqlite3.Row; return x

def ensure_schema():
 d=db(); cols={r['name'] for r in d.execute('PRAGMA table_info(users)').fetchall()}
 if 'specialty' not in cols: d.execute("ALTER TABLE users ADD COLUMN specialty TEXT DEFAULT 'general'")
 if 'whatsapp_template' not in cols: d.execute("ALTER TABLE users ADD COLUMN whatsapp_template TEXT")
 d.execute('CREATE INDEX IF NOT EXISTS idx_companies_assigned ON companies(assigned_user_id)')
 d.execute('CREATE INDEX IF NOT EXISTS idx_interactions_company ON interactions(company_id, contacted_at)')
 d.commit(); d.close()
ensure_schema()

def login_required(f):
 @wraps(f)
 def w(*a,**k):
  if 'uid' not in session:return redirect(url_for('login'))
  return f(*a,**k)
 return w

def admin_required(f):
 @wraps(f)
 def w(*a,**k):
  if 'uid' not in session:return redirect(url_for('login'))
  if session.get('role')!='admin': abort(403)
  return f(*a,**k)
 return w

def scoped_company(d,cid):
 # جميع المستخدمين يمكنهم مشاهدة جميع العملاء. التوزيع يبقى للتنظيم والإحصائيات فقط.
 return d.execute('SELECT c.*,u.name rep FROM companies c LEFT JOIN users u ON u.id=c.assigned_user_id WHERE c.id=?',(cid,)).fetchone()

def wa_text(user_row, company_name):
 specialty=(user_row['specialty'] or 'general') if user_row else 'general'; template=(user_row['whatsapp_template'] or '').strip() if user_row else ''
 if not template: template=DEFAULT_MESSAGES.get(specialty,DEFAULT_MESSAGES['general'])
 return template.replace('{{rep_name}}','{rep_name}').replace('{{company_name}}','{company_name}').format(rep_name=user_row['name'] if user_row else session.get('name',''),company_name=company_name or 'شركتكم')
def wa_link(phone,text):
 if not phone:return None
 p=''.join(ch for ch in phone if ch.isdigit())
 if p.startswith('05'): p='966'+p[1:]
 elif p.startswith('5') and len(p)==9: p='966'+p
 return 'https://wa.me/'+p+'?text='+urllib.parse.quote(text)

@app.context_processor
def ctx(): return {'status':STATUS,'status_class':STATUS_CLASS,'specialties':SPECIALTIES,'user':session.get('name')}
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  d=db(); u=d.execute('SELECT * FROM users WHERE email=? AND active=1',(request.form['email'],)).fetchone(); d.close()
  if u and check_password_hash(u['password_hash'],request.form['password']): session.clear(); session.update(uid=u['id'],name=u['name'],role=u['role']); return redirect(url_for('dashboard'))
  flash('بيانات الدخول غير صحيحة')
 return render_template('login.html')
@app.get('/health')
def health(): return jsonify({'status':'ok'})
@app.get('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.get('/')
@login_required
def dashboard():
 d=db(); is_admin=session.get('role')=='admin'; scope='' if is_admin else ' WHERE assigned_user_id=?'; args=[] if is_admin else [session['uid']]
 total=d.execute('SELECT COUNT(*) n FROM companies'+scope,args).fetchone()['n']
 counts={k:d.execute('SELECT COUNT(*) n FROM companies'+((' WHERE ' if is_admin else ' WHERE assigned_user_id=? AND ')+'marketing_status=?'),([] if is_admin else [session['uid']])+[k]).fetchone()['n'] for k in STATUS}
 if is_admin:
  follow=d.execute("SELECT COUNT(DISTINCT company_id) n FROM interactions WHERE next_followup_at IS NOT NULL AND datetime(next_followup_at)<=datetime('now','localtime')").fetchone()['n']
  reps=d.execute("SELECT u.id,u.name,u.role,COUNT(c.id) n,SUM(CASE WHEN c.marketing_status='contacted' THEN 1 ELSE 0 END) contacted,SUM(CASE WHEN c.marketing_status='interested' THEN 1 ELSE 0 END) interested,SUM(CASE WHEN c.marketing_status='contracted' THEN 1 ELSE 0 END) contracted,(SELECT MAX(i.contacted_at) FROM interactions i WHERE i.user_id=u.id) last_contact FROM users u LEFT JOIN companies c ON c.assigned_user_id=u.id WHERE u.active=1 GROUP BY u.id ORDER BY n DESC").fetchall()
 else:
  follow=d.execute("SELECT COUNT(DISTINCT i.company_id) n FROM interactions i JOIN companies c ON c.id=i.company_id WHERE c.assigned_user_id=? AND i.next_followup_at IS NOT NULL AND datetime(i.next_followup_at)<=datetime('now','localtime')",(session['uid'],)).fetchone()['n']; reps=[]
 recent=d.execute("SELECT c.id,c.name_ar,c.name_en,i.channel,i.outcome,i.contacted_at,i.next_followup_at FROM interactions i JOIN companies c ON c.id=i.company_id WHERE "+("1=1" if is_admin else "c.assigned_user_id=?")+" ORDER BY i.contacted_at DESC LIMIT 10",[] if is_admin else [session['uid']]).fetchall(); d.close()
 return render_template('dashboard.html',counts=counts,total=total,follow=follow,reps=reps,recent=recent,is_admin=is_admin)

@app.get('/companies')
@login_required
def companies():
 q=request.args.get('q','').strip(); city=request.args.get('city','').strip(); st=request.args.get('status','').strip(); rep=request.args.get('rep','').strip(); page=max(1,int(request.args.get('page',1))); per=50; where=[]; args=[]
 if session.get('role')=='admin' and rep:
  if rep=='unassigned': where.append('c.assigned_user_id IS NULL')
  else: where.append('c.assigned_user_id=?'); args.append(rep)
 if q: where.append('(c.name_ar LIKE ? OR c.name_en LIKE ? OR c.phone_mobile LIKE ? OR c.phone_landline LIKE ? OR c.email LIKE ?)'); args += [f'%{q}%']*5
 if city: where.append('c.city=?'); args.append(city)
 if st: where.append('c.marketing_status=?'); args.append(st)
 w=(' WHERE '+' AND '.join(where)) if where else ''; d=db(); total=d.execute('SELECT COUNT(*) n FROM companies c'+w,args).fetchone()['n']
 sql="""SELECT c.*,u.name rep,(SELECT i.contacted_at FROM interactions i WHERE i.company_id=c.id ORDER BY i.contacted_at DESC LIMIT 1) last_contact,(SELECT i.next_followup_at FROM interactions i WHERE i.company_id=c.id AND i.next_followup_at IS NOT NULL ORDER BY i.contacted_at DESC LIMIT 1) next_followup FROM companies c LEFT JOIN users u ON u.id=c.assigned_user_id"""+w+' ORDER BY c.id LIMIT ? OFFSET ?'
 rows=[dict(r) for r in d.execute(sql,args+[per,(page-1)*per]).fetchall()]; cities=d.execute("SELECT DISTINCT city FROM companies WHERE city IS NOT NULL AND city<>'' ORDER BY city").fetchall(); me=d.execute('SELECT * FROM users WHERE id=?',(session['uid'],)).fetchone(); users=d.execute("SELECT id,name FROM users WHERE active=1 ORDER BY name").fetchall() if session.get('role')=='admin' else []; d.close()
 for r in rows: r['wa_link']=wa_link(r.get('whatsapp') or r.get('phone_mobile'),wa_text(me,r.get('name_ar') or r.get('name_en')))
 return render_template('companies.html',rows=rows,total=total,page=page,per=per,q=q,city=city,status_filter=st,rep_filter=rep,cities=cities,users=users,is_admin=session.get('role')=='admin')

@app.post('/companies/assign')
@admin_required
def assign_companies():
 ids=[int(x) for x in request.form.getlist('company_ids') if x.isdigit()]; uid=request.form.get('assigned_user_id')
 if not ids: flash('حدد عميلاً واحداً على الأقل'); return redirect(request.referrer or url_for('companies'))
 d=db(); valid=d.execute('SELECT id FROM users WHERE id=? AND active=1',(uid,)).fetchone() if uid else None
 if uid and not valid: d.close(); abort(400)
 ph=','.join('?'*len(ids)); d.execute(f'UPDATE companies SET assigned_user_id=?,updated_at=CURRENT_TIMESTAMP WHERE id IN ({ph})',[uid or None]+ids); d.commit(); d.close(); flash(f'تم توزيع {len(ids)} عميل بنجاح'); return redirect(request.referrer or url_for('companies'))

@app.get('/company/<int:cid>')
@login_required
def company(cid):
 d=db(); c=scoped_company(d,cid)
 if not c: d.close(); abort(404)
 its=d.execute('SELECT i.*,u.name rep FROM interactions i LEFT JOIN users u ON u.id=i.user_id WHERE company_id=? ORDER BY contacted_at DESC',(cid,)).fetchall(); users=d.execute('SELECT * FROM users WHERE active=1').fetchall() if session.get('role')=='admin' else []; me=d.execute('SELECT * FROM users WHERE id=?',(session['uid'],)).fetchone(); d.close(); link=wa_link(c['whatsapp'] or c['phone_mobile'],wa_text(me,c['name_ar'] or c['name_en']))
 return render_template('company.html',c=c,its=its,users=users,wa_link=link,is_admin=session.get('role')=='admin')

@app.post('/company/<int:cid>/update')
@login_required
def update_company(cid):
 d=db(); c=scoped_company(d,cid)
 if not c: d.close(); abort(404)
 if session.get('role')=='admin':
  assigned=request.form.get('assigned_user_id') or None
  d.execute('UPDATE companies SET marketing_status=?,assigned_user_id=?,priority=?,marketing_notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(request.form['marketing_status'],assigned,request.form.get('priority','normal'),request.form.get('marketing_notes',''),cid))
 else:
  d.execute('UPDATE companies SET marketing_status=?,priority=?,marketing_notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(request.form['marketing_status'],request.form.get('priority','normal'),request.form.get('marketing_notes',''),cid)); d.commit(); d.close(); return redirect(url_for('company',cid=cid))

@app.post('/company/<int:cid>/interaction')
@login_required
def interaction(cid):
 d=db(); c=scoped_company(d,cid)
 if not c: d.close(); abort(404)
 d.execute('INSERT INTO interactions(company_id,user_id,channel,outcome,notes,next_followup_at) VALUES(?,?,?,?,?,?)',(cid,session['uid'],request.form['channel'],request.form['outcome'],request.form.get('notes',''),request.form.get('next_followup_at') or None)); d.execute('UPDATE companies SET marketing_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(request.form['outcome'],cid)); d.commit(); d.close(); return redirect(url_for('company',cid=cid))

@app.post('/company/<int:cid>/quick-followup')
@login_required
def quick_followup(cid):
 d=db(); c=scoped_company(d,cid)
 if not c: d.close(); abort(404)
 when=request.form.get('next_followup_at') or None; notes=request.form.get('notes','متابعة سريعة')
 d.execute("INSERT INTO interactions(company_id,user_id,channel,outcome,notes,next_followup_at) VALUES(?,?,?,?,?,?)",(cid,session['uid'],'متابعة','followup',notes,when)); d.execute("UPDATE companies SET marketing_status='followup',updated_at=CURRENT_TIMESTAMP WHERE id=?",(cid,)); d.commit(); d.close(); flash('تم تسجيل المتابعة السريعة'); return redirect(request.referrer or url_for('companies'))

@app.get('/users')
@admin_required
def users():
 d=db(); rows=d.execute('SELECT id,name,email,role,active,specialty,whatsapp_template FROM users ORDER BY id').fetchall(); d.close(); return render_template('users.html',rows=rows,default_messages=DEFAULT_MESSAGES)
@app.post('/users/add')
@admin_required
def add_user():
 specialty=request.form.get('specialty','general'); template=request.form.get('whatsapp_template','').strip() or DEFAULT_MESSAGES.get(specialty,DEFAULT_MESSAGES['general']); d=db(); d.execute('INSERT INTO users(name,email,password_hash,role,specialty,whatsapp_template) VALUES(?,?,?,?,?,?)',(request.form['name'],request.form['email'],generate_password_hash(request.form['password']),request.form['role'],specialty,template)); d.commit(); d.close(); return redirect(url_for('users'))
@app.post('/users/<int:uid>/update')
@admin_required
def update_user(uid):
 specialty=request.form.get('specialty','general'); template=request.form.get('whatsapp_template','').strip() or DEFAULT_MESSAGES.get(specialty,DEFAULT_MESSAGES['general']); d=db(); d.execute('UPDATE users SET specialty=?,whatsapp_template=? WHERE id=?',(specialty,template,uid)); d.commit(); d.close(); flash('تم تحديث اختصاص ورسالة المستخدم'); return redirect(url_for('users'))

@app.get('/export')
@login_required
def export():
 d=db(); rows=d.execute('SELECT * FROM companies ORDER BY id').fetchall(); out=io.StringIO(); w=csv.writer(out); w.writerow(rows[0].keys() if rows else ['id']); [w.writerow(list(r)) for r in rows]; d.close(); return Response('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=companies.csv'})
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
