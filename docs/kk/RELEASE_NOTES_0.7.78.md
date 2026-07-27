# GEOLOG GASRATIO@Pixler 0.7.78 — WITS0 сенімділігі және қалпына келтіру

Тұрақты connection ID, append-only JSONL қосылым журналы және ашық acquisition session ішіндегі
типтелген connection records қосылды. Raw жазу алдындағы диск бақылауы және тек белсенді емес
сегменттерді өшіретін retention енгізілді. Атомарлық recovery manifest және `.wits` байттарын
өзгертпей қиылған chunk-index соңын түзету қолжетімді.

Ашық WITS0 сессиясы immutable schema және versioned custom profile арқылы sequence/checkpoints
үздіксіздігімен жалғасады. Live axis/follow/pause/history/curve күйі әр ұңғыма үшін сақталады.
Reconnect, chunking, gaps, duplicates және malformed values үшін headless Python және PowerShell
Windows soak құралдары қосылды.

Project format v20 болып қалады. Нақты GSWITS soak, физикалық disk-full, Windows Service және signed
field checklist бұл релизде өтті деп жарияланбайды.
