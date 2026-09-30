V7.5.40
إصلاح خطأ Internal Server Error في صفحة استعادة كلمة المرور.
السبب: secrets.compare_digest مستخدمة للتحقق الآمن من ADMIN_RECOVERY_KEY
لكن مكتبة secrets لم تكن مستوردة في app.py.
تم إصلاح الاستيراد فقط مع الإبقاء على:
- 15,895 شركة
- 5 سجلات تواصل المستعادة
- استعادة JSON
- ADMIN_RECOVERY_KEY
- جميع خصائص V7.5.39
