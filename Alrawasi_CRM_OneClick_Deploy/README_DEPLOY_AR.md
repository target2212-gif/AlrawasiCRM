# تلال الرواسي CRM — جاهز للنشر على Render

هذه النسخة مضبوطة لتعمل مع بنية المستودع الحالية:

AlrawasiCRM/
└── Alrawasi_CRM_OneClick_Deploy/
    ├── render.yaml
    ├── Dockerfile
    ├── app.py
    ├── requirements.txt
    ├── crm.db
    └── templates/

## الإعداد المطلوب في Render

Blueprint Path:
`Alrawasi_CRM_OneClick_Deploy/render.yaml`

ثم اضغط Retry / Apply.

تم ضبط `rootDir` داخل `render.yaml` ليشير إلى:
`Alrawasi_CRM_OneClick_Deploy`

## بيانات الدخول الأولية

- البريد: `admin@alrawasi.local`
- كلمة المرور: `ChangeMe123!`

غيّر كلمة المرور بعد أول دخول.

## تنبيه مهم عن قاعدة البيانات

التطبيق يستخدم SQLite (`crm.db`). على خطة Render المجانية قد لا تبقى التغييرات التي تُكتب إلى
قاعدة البيانات بعد إعادة النشر أو إعادة تشغيل الخدمة. قاعدة البيانات المرفقة مناسبة للتجربة،
أما الاستخدام الإنتاجي الدائم فيحتاج تخزينًا دائمًا أو قاعدة بيانات خارجية مثل PostgreSQL.
