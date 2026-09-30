# V7.5.43 — Persistent Contact Ledger

سبب الإصدار:
Render Free يستخدم filesystem مؤقت. عند spin-down أو restart أو redeploy يتم فقد crm.db
الحي وإعادة بنائه من seed. هذا كان يحذف سجلات التواصل الجديدة.

ما تم إصلاحه:
- استعادة 3 سجلات تواصل مفقودة من Snapshot 2026-09-27 ودمجها مع أحدث Snapshot.
- أصبح seed يحتوي 11 سجل تواصل بدلاً من 8.
- إضافة remote_event_id ثابت لكل سجل تواصل.
- إضافة سجل تواصل دائم في PostgreSQL خارجي عبر CONTACTS_DATABASE_URL.
- عند كل تواصل/متابعة جديدة: يحفظ الحدث في PostgreSQL ثم في SQLite.
- عند تشغيل التطبيق: يرفع السجلات المحلية القديمة إلى PostgreSQL، ثم يستعيد أي سجلات
  دائمة مفقودة في SQLite تلقائياً.
- حذف سجل تواصل ينشئ tombstone دائم حتى لا يعود السجل بعد restart.
- حالة الشركة تستعاد من آخر حدث تواصل دائم.
- يظهر للمدير شريط أخضر إذا الحماية مفعلة وأحمر إذا لم يتم ضبط PostgreSQL.

الإعداد المطلوب:
1) أنشئ PostgreSQL دائم لدى أي مزود خارجي.
2) خذ Connection String الكامل بصيغة postgresql://...
3) Render > Service > Environment
4) أضف:
   CONTACTS_DATABASE_URL = connection string
5) لا ترسل connection string أو كلمة مرور قاعدة البيانات في المحادثة.
6) Deploy V7.5.43.

مهم:
- بدون CONTACTS_DATABASE_URL سيظل التطبيق يعمل، لكن Render Free سيظل يفقد التغييرات المحلية.
- لا تستخدم Render Key Value Free لحفظ السجل لأنه غير دائم عند restart.
