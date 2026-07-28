# WITSML 1.4.1.1 SOAP тек оқу интеграциясы

## Қолдау аумағы

Тек `WMLS_GetVersion`, `WMLS_GetCap` және `WMLS_GetFromStore` қолданылады. Add, Update және Delete
операциялары жоқ. Иерархия:

`Well → Wellbore → Log → LogCurveInfo → LogData`.

## Қауіпсіздік шекарасы

- URL ішінде пайдаланушы аты немесе құпиясөз болмауы тиіс;
- құпиясөз профильге және жобаға сериализацияланбайды;
- Windows Credential Manager қолданылады;
- SOAP ішіндегі DTD/entity қабылданбайды;
- жауап өлшемі шектеледі;
- аудит XML сұрауын және Authorization мәнін сақтамайды;
- remote endpoint тек certificate chain және hostname verification бар `https://` арқылы
  рұқсат етіледі;
- `http://` немесе TLS verification өшіру тек loopback (`127.0.0.1`/`localhost`) және
  бақыланатын test үшін жарамды;
- HTTP redirects орындалмайды: credentials басқа origin немесе downgrade ішіне өтпеуі үшін
  final URL-ді енгізіп, бөлек растаңыз.

Certificate error болса, жұмысты тоқтатып, server administrator-ға хабарласыңыз. Password-ты URL
ішіне жазбаңыз және remote address үшін verification өшірмеңіз.

## Қайталау саясаты

Тек уақытша желі қателері және таңдалған HTTP кодтары қайталанады. SOAP Fault және теріс WITSML
Result қайталанбайды. Әр әрекет аудитке бөлек жазылады.

## Импорт жолы

LogData жолдары CSV ретінде оқылады. Индекс `indexCurve` немесе бірінші mnemonic бойынша алынады.
`logCurveInfo/nullValue` null мәніне айналады. Log `WitsmlChannelSetData` моделіне бейімделіп,
қолданыстағы Import Review және атомарлық жоба тіркеуінен өтеді.
