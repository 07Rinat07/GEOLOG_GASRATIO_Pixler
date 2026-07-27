# GEOLOG GASRATIO@Pixler 0.7.79 — WITSML 2.x ChannelSet импорты

Ішкі және салыстырмалы файлдағы WITSML 2.x ChannelData array қауіпсіз офлайн оқуы, ChannelSet,
index және channel таңдауы, қатаң UOM нормализациясы, semantic Import Review және детерминирленген
Dataset provenance қосылды. Толық immutable Dataset жоба өзгермей тұрып құрылады, ал оператор
тексерген commit атомарлық project controller арқылы бір рет тіркеледі.

Жарамсыз index бар жолдар review ішінде көрінеді және нақты саясатпен ғана алынып тасталады.
Қолдау көрсетілмейтін array немесе UOM келісімі болжаммен өңделмей, commit-ті блоктайды. XML/ZIP
лимиттері, traversal protection, source/data SHA-256 және Dataset digest сақталады.

Project format v20 болып қалады. Нақты GSWITS бар Windows reliability gate бөлек және параллель
орындалады; бұл релиз checklist пен бұрынғы soak құралдарын ғана береді.
