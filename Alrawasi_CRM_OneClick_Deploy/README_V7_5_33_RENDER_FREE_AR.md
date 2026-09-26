# V7.5.33 — Render Free Safe Baseline
- مبني على Snapshot المنقح V7.5.31 الذي رفعه المستخدم.
- قاعدة crm.db المضمنة أعيد تكوينها من الـSnapshot المنقح، لا من دليل الشركات القديم.
- لا يعتمد على /var/data لأن Render Free لا يوفر Persistent Disk.
- زر نسخة JSON مستمر.
- صفحة حماية Free جديدة: تنزيل Snapshot واستعادة Snapshot كاملة.
- قبل أي استعادة JSON ينشئ النظام نسخة SQLite داخل الحاوية.
- بعد كل تنقيح مهم: نزّل Snapshot JSON واحتفظ به خارج Render.
