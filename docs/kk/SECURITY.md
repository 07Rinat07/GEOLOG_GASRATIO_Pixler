# Қолданбамен қауіпсіз жұмыс істеу

Бұл нұсқаулық GEOLOG GASRATIO@Pixler пайдаланушылары мен әкімшілеріне арналған. Қолданба
well-control немесе emergency-shutdown system емес, decision-support tool болып табылады.
Төмендегі нұсқаулармен бірге ұйымыңыздың access, backup және геологиялық деректерді өңдеу
ережелерін қолданыңыз.

2026 жылғы 28 шілдеде **P0 repository incident** әлі ашық: `project.geolog.json` және бес
LAS-related sidecar ағымдағы Git index-тен алынып, `.gitignore` ережелерімен қорғалды, бірақ
бұрын жарияланған history-де нақты well data-ға ұқсайтын шамамен 31,8 MB материал мен local
absolute paths әлі болуы мүмкін. Data owner classification туралы шешім қабылдап, history
тазаланғанға дейін бұл artifacts-ті clone, mirror немесе redistribute жасамаңыз.

## Деректерді ашу немесе импорттау алдында

LAS, GS2/Paradox, WITSML XML/ZIP/EPC, projects, forms, SVG және images көздері расталғанға дейін
сенімсіз деп есептеңіз.

1. Көшірмемен жұмыс істеп, жіберуші берген fingerprint/SHA-256 мәнін сақтаңыз.
2. Файлды тек белгілі контрагенттен қабылдап, күтілетін түрі мен өлшемін тексеріңіз.
3. Commit алдында Import Review арқылы well, index, mnemonics, UOM, NULL, warnings және row
   count мәндерін тексеріңіз.
4. Archive күтпегендей үлкен болса, белгісіз paths қамтыса, network access сұраса,
   DTD/entity/external-reference қатесін көрсетсе немесе күтілгеннен көп объект өзгертсе, import
   әрекетін тоқтатыңыз.
5. Imported content ішіндегі macros/scripts қоспаңыз және external links ашпаңыз.

Parser сәтті аяқталуы деректің дұрыстығын дәлелдемейді. Critical channels және intervals-ті source
report-пен салыстырыңыз. Export бөлек файл жасайды және project үшін **Ctrl+S** әрекетін
алмастырмайды.

## LAS/XML ерте лимиттері

LAS `lasio` іске қосылмай тұрып bounded streaming оқуынан өтеді; лимиттен асқан файл уақытша
Dataset құрмайды. WITSML 2.x inventory/data import және WITSML 1.4.1.1 SOAP бір streaming XML
parser қолданады. Ол byte, depth, element, text және attribute лимиттері бойынша тоқтайды, ал
DTD/entity/external entity/notation толық tree құрылмай тұрып тыйым салынады. Лимиттерді тек
расталған source және нақты memory budget болғанда үлкейтіңіз.

## WITS0: тек жергілікті немесе оқшауланған желі

WITS Level 0 ішінде кірістірілген encryption және authentication жоқ.

- GSWITS сол компьютерде жұмыс істесе, TCP server адресін әдепкі `127.0.0.1` күйінде қалдырыңыз.
- Бөлек компьютер үшін сенімді интерфейстің нақты адресін көрсетіңіз.
- `0.0.0.0` тек физикалық немесе логикалық оқшауланған сенімді желіде, firewall allowlist және
  айқын рұқсат болғанда пайдаланыңыз.
- WITS0 port-ты интернетке ешқашан ашпаңыз; public-cloud listener немесе router port-forward
  баптамаңыз.
- Field capture алдында IP/port, source owner, raw directory, free disk space және
  stop/recovery plan растаңыз.

Белгісіз peer қосылса, capture тоқтатып, journal мен raw segments сақтаңыз, интерфейсті
оқшаулаңыз және әкімшіге хабарлаңыз. Triage алдында evidence жоймаңыз.

## Қашықтағы WITSML және ETP

- Remote WITSML SOAP тек **HTTPS**, ETP тек **WSS** арқылы, certificate және hostname verification
  қосылған күйде рұқсат етіледі.
- Certificate error, мерзімінің аяқталуы немесе күтпеген hostname — verification өшіруге емес,
  жұмысты тоқтатуға себеп.
- HTTP/WS немесе verification өшіру тек loopback (`127.0.0.1`/`localhost`) және бақыланатын test
  fixtures үшін жарамды.
- Redirects орындалмайды. Final endpoint-ті әкімшіден растаңыз; credentials-ті басқа URL-ге
  қолмен көшірмеңіз.
- Күтілетін Well/Wellbore шегіндегі least-privilege read-only account қолданыңыз. Time,
  response size және retry count шектеңіз.
- ETP profile ішінде бір message, multipart жалпы encoded көлемі, parts саны және assembly time
  үшін бөлек limits орнатыңыз. Кез келген multipart limit асса pending requests аяқталып, session
  жабылады; нақты operational қажеттілік болмаса бұл мәндерді үлкейтпеңіз.

Unknown project, email немесе diagnostic bundle ішінен алынған endpoint-ке server owner оны бөлек
сенімді арнамен растамайынша қосылмаңыз.

## Credentials және secrets

Passwords және tokens операциялық жүйенің credential store арқылы сақталсын. Windows жүйесінде
Windows Credential Manager қолданылады.

- password-ты URL, profile name, project file, comment, screenshot немесе ticket ішіне жазбаңыз;
- test және production үшін бір credential қолданбаңыз;
- пайдаланылмайтын entry-ді credential store ішінен өшіріп, server-side access қайтарып алыңыз;
- leakage күдігі болса, remote connection тоқтатып, secret ауыстырыңыз және әкімшіге хабарлаңыз;
- project жіберер алдында алушыға бөлек рәсіммен тек қажетті rights берілгенін тексеріңіз.

Connection profile жою операциялық жүйедегі credential-ды міндетті түрде жоймайды; credential
store-ды бөлек тексеріңіз.

## Diagnostics және privacy

Logs және diagnostic bundles passwords алып тасталған жағдайда да local paths, user names,
server addresses, well identifiers, mnemonics және measurement samples қамтуы мүмкін.

1. Ең қысқа пайдалы interval жинап, мүмкін болса мәселені anonymized copy арқылы қайталаңыз.
2. Жіберер алдында әр файлды қарап, credentials, tokens, personal data, commercial names және
   мәселеге қатысы жоқ raw values алып тастаңыз.
3. Original evidence-ті орнында өзгертпеңіз. Қорғалған original сақтап, өзгерістері белгіленген
   бөлек sanitized copy жасаңыз.
4. Bundle-ды тек мақұлданған protected channel арқылы, тек көрсетілген recipients-ке жіберіңіз.
5. Case жабылғаннан кейін temporary copies-ті қолданыстағы retention policy бойынша жойыңыз.

Raw WITS0, GS2 немесе толық projects тек data owner рұқсатымен жіберіледі. Қалыпты report үшін
version, UTC time, minimal steps, sanitized log және artifact hashes жеткілікті болуы тиіс.

## Осалдық немесе incident туралы хабарлау

Build distributor немесе ұйым әкімшісі жариялаған private security channel қолданыңыз. Егер
арнайы address әлі жарияланбаса, жауапты maintainer-ге жеке хабарласыңыз; email ойдан шығармаңыз
және exploit, credentials, нақты raw data немесе түзетілмеген vulnerability report-ты public issue
ішіне салмаңыз.

Мыналарды қосыңыз:

- package version, operating system және installation method;
- қысқаша impact және affected boundary: import, project, WITS0, WITSML/ETP, export немесе update;
- minimal reproduction steps және safe synthetic fixture;
- sanitized diagnostics, UTC time және artifact hashes;
- credentials бұзылуы мүмкін бе деген ақпарат, бірақ secret values қоспаңыз.

Active incident кезінде алдымен external connections тоқтатып, read-only evidence сақтаңыз.
Owner рұқсатынсыз production server үстінде test жалғастырмаңыз.

Белгілі repository incident үшін maintainer және data owner:

1. data, exposure window, affected commits/clones/releases және notification duties classify
   жасауы;
2. triage кезінде access дереу шектеуі немесе remote-ты private етуі;
3. explicit authorization кейін ғана current artifacts алып тастап, дәл `.gitignore` rules қосып,
   барлық affected Git history қайта жазуы;
4. remote caches, forks, mirrors, CI artifacts және release archives purge сұрап, қолжетімді
   copies тексеруі;
5. real material-ды explicit provenance бар minimal synthetic fixtures-пен ауыстыруы тиіс.

Files-ті тек HEAD ішінен жою жеткіліксіз: earlier commits және external copies content-ті ашық
қалдырады. Data owner және incident-response lead-пен келіспей history rewrite жасамаңыз немесе
evidence жоймаңыз.

## Пакетті шығару алдындағы тексеру

Release build тек тексерілген runtime `requirements/release.lock` файлы бойынша таза
Windows x86-64/Python 3.11 ортасында жасалады. Lock-файлдағы әр application dependency нақты
version және SHA-256 hash арқылы бекітіледі; орнату `--require-hashes` параметрімен орындалады,
содан кейін жобаның өзі `--no-deps` және build isolation қолданбай орнатылады. CI tools бөлек
нақты versions арқылы орнатылады және таратылатын application graph құрамына кірмейді.

Шығару алдында толық quality gate және `python tools/release_security_gate.py` орындалады.
Security командасы dependency audit JSON, CycloneDX JSON SBOM, `detect-secrets` нәтижесін,
Bandit JSON және lock-файлдың SHA-256 мәні мен exit codes бар manifest жасайды. Нәтижелер тек Git
елемейтін `build/ci-artifacts` ішінде және CI artifacts ретінде сақталады. Оларды commit жасауға,
`docs` ішіне көшіруге немесе міндетті тексерудің коды нөл болмаса successful деп санауға болмайды.

## Field іске қосу алдындағы checklist

- белгілі repository incident classify жасалды, remote шектелді және real fixtures жаңа
  commits-ке кірмейді;
- file sources және network peers расталды;
- WITS0 loopback немесе isolated allowlisted network ішінде қалды;
- remote WITSML/ETP redirects жоқ verified HTTPS/WSS қолданады;
- credentials тек system store ішінде және minimum rights-пен сақталады;
- raw/project directories қорғалған, free space және backup тексерілген;
- diagnostic sharing ережелері мен incident contacts келісілген;
- баптаудан кейін test capture, controlled close, **Ctrl+S** және reopen орындалды.
