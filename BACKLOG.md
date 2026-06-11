# Backlog — Share of AI

Tracciamento di problemi noti e migliorie da affrontare in sessioni dedicate.
Aggiornato: 2026-06-11.

## 🔴 Priorità alta (robustezza)

- [ ] **Validazione credenziali all'avvio** — `APOLLO_CLIENT_ID/SECRET` e `TAVILY_API_KEY`
  sono caricate con default vuoti e mai validate (`config.py`); errori a runtime poco chiari.
  Aggiungere check all'avvio con messaggio chiaro in UI.
- [ ] **Autosave path hardcoded `/tmp`** (`app.py`) — non persistente al reboot, problematico
  multi-utente; eccezione di scrittura silenziata (`except: pass`). Spostare in una
  directory dati del progetto e segnalare i fallimenti.
- [ ] **Schema mismatch `source_evaluation`** — il system prompt richiede
  `source_strength_reason`, `tone_detected`, `decisive_factor` ma `core/parser.py` valida
  solo `source_strength` e `tone_alignment`; risposte incomplete passano la validazione
  e la UI assume che i campi esistano.

## 🟡 Priorità media (pulizia e coerenza)

- [ ] Import morti: `lru_cache` in `core/web_search.py`, `run_parallel` in `app.py`.
- [ ] `altair` usato in `app.py` ma assente da `requirements.txt` (oggi è dipendenza
  transitiva di Streamlit — esplicitarla).
- [ ] Deserializzazione JSON incoerente: `json_to_results` usa `json.loads` raw mentre
  altrove si usa `parse_json_response`; uniformare la gestione errori.
- [ ] Pattern `del st.session_state[...]` + `st.rerun()` in più punti: usare `.pop(..., None)`
  per evitare KeyError in edge case.

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
