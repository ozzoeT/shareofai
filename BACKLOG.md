# Backlog — Share of AI

Tracciamento di problemi noti e migliorie da affrontare in sessioni dedicate.
Aggiornato: 2026-06-11.

## ✅ Fase 0 — completata (commit 3120e6e)

- [x] **Validazione credenziali all'avvio** — check su `APOLLO_CLIENT_ID/SECRET` e
  `TAVILY_API_KEY` con messaggi chiari in UI (`app.py`).
- [x] **Autosave path hardcoded `/tmp`** — spostato in `autosave/` (gitignored),
  errori di scrittura segnalati con `st.warning`.
- [x] **Schema mismatch `source_evaluation`** — `core/parser.py` ora valida i tipi di
  `source_strength_reason`, `tone_detected`, `decisive_factor`.
- [x] Import morti rimossi (`lru_cache`, `run_parallel`).
- [x] `altair` aggiunto a `requirements.txt`.
- [x] `del st.session_state[...]` → `.pop(..., None)`.
- [x] Suite pytest minima (`tests/`) + CI GitHub Actions.

## 🟡 Priorità media (pulizia e coerenza)

- [ ] Deserializzazione JSON: `json_to_results` legge l'envelope salvato dall'app con
  `json.loads` diretto (corretto, è formato nostro non output LLM) — nessuna azione
  necessaria, chiuso come non-issue.

## 🟢 Scalabilità / produzione (vedi anche recap simulazione→produzione in chat)

- [ ] Nessuna suite di test né CI — aggiungere pytest su `core/` (parser, brand_groups,
  web_search cache) e una GitHub Action.
- [ ] Architettura tutta in-memory/file JSON (risultati, prompt, brand groups, contatore
  Tavily): single-user only. Per multi-utente serve un DB (SQLite come primo passo).
- [ ] Possibile prompt injection dai web snippet iniettati nei prompt di analisi —
  rischio basso in uso interno, da mitigare prima di esporre a terzi.
- [ ] Cache Tavily solo in-memory per processo: renderla persistente con TTL.
- [ ] Storico run: confronto tra run nel tempo (trend "share of AI" per brand), non solo
  ultima run.

## 💡 Idee prodotto (da valutare)

- [ ] Scheduling di run ricorrenti (monitoraggio settimanale automatico).
- [ ] Report PDF/HTML brandizzato esportabile per i clienti.
- [ ] Multi-tenant: workspace per cliente con catalogo brand proprio.
- [ ] Benchmark competitivo: alert quando un competitor supera il brand del cliente
  su un tono/categoria.
- [ ] Estendere oltre il veterinario: il system prompt è l'unico punto verticale,
  parametrizzare il dominio.
