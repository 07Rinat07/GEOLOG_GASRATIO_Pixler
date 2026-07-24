# GEOLOG GASRATIO@Pixler 0.7.59

Critical form-switching hotfix. Dense tracks with internally scrollable headers accessed a missing `TabletTrackWidget._localizer`, causing form application to fail and rollback. Every rendered track now receives the active localizer before header population, while direct construction uses a safe fallback. Project format v20, form schema v6, and tablet layout v16 are unchanged.
