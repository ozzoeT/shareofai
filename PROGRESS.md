# Share of AI — Progress Tracker

## Obiettivo
Pipeline per testare in parallelo diversi LLM simulando il comportamento di un utente che chiede suggerimenti d'acquisto di prodotti veterinari.
Studio di quali brand vengono preferiti (e con quale confidenza) dai vari modelli, con e senza ricerca web.

---

## Piano di sviluppo

### FASE 1 — Struttura progetto & core layer ✅ COMPLETATA
Riorganizzare il codice dal notebook in moduli Python puliti.
- [x] `core/client.py` — Apollo client (astrazione OpenAI-compatible)
- [x] `core/runner.py` — test runner con esecuzione parallela dei modelli (ThreadPoolExecutor)
- [x] `core/parser.py` — parsing e validazione JSON delle risposte
- [x] `core/prompt_builder.py` — generazione prompt per tono/lingua via LLM
- [x] `core/web_search.py` — stub predisposto per Fase 4
- [x] `config.py` — configurazione modelli, path, parametri
- [x] `data/` — system_prompt.txt e prompts.json

### FASE 2 — Interfaccia Streamlit (base) ✅ COMPLETATA
App web per mostrare l'idea e il prototipo.
- [x] Pagina intro: spiegazione del concetto
- [x] Sidebar: selezione modelli, temperatura, max_tokens
- [x] Tab "Run Test": filtri per tono/lingua, anteprima prompt, esecuzione, tabella risultati
- [x] Tab "Prompts": libreria prompt + generazione via LLM + salvataggio
- [x] Tab "Results": pivot brand×model, confidence media, dettaglio risposta

### FASE 3 — Generazione prompt ✅ COMPLETATA (integrata in Fase 2)
Possibilità di creare nuovi prompt variando tono, lingua e scenario.
- [x] Form per topic + tono + lingua
- [x] Generazione via LLM (generate_prompt_via_llm)
- [x] Salvataggio nella libreria prompt (prompts.json)

### FASE 4 — Ricerca web (predisposta, da implementare)
Aggiunta del tool di ricerca web per simulare l'esperienza reale su piattaforme complete.
- [x] Architettura stub in `core/web_search.py`
- [x] Flag `web_search_used` in ModelResult
- [x] Toggle UI in sidebar (disabilitato finché WEB_SEARCH_ENABLED=False)
- [ ] Implementare provider (Tavily / Bing / Google Custom Search)
- [ ] Tool calling per modelli che lo supportano
- [ ] Confronto risultati pre/post web search

---

## Log sessioni

### Sessione 1 — 2026-05-06
**Stato iniziale:** Draft su Jupyter notebook (`share_of_AI_test.ipynb`)
- Apollo client funzionante (OAuth2 + OpenAI-compatible interface)
- 2 modelli testati: `claude_3_5_haiku`, `gpt-4o-mini`
- 9 prompt di esempio in IT/EN con 4 toni (concise, detailed, reassuring, technical)
- System prompt per prodotti veterinari con output JSON strutturato
- Parser JSON robusto e validatore schema

**Decisione architetturale:** usare Apollo come gateway LLM unificato (già supporta Claude + GPT).
La web search sarà un layer separato predisposto ma non ancora implementato.

**Lavoro svolto:**
- Lettura e analisi del draft esistente
- Creazione piano di sviluppo (questo file)
- Implementate Fasi 1, 2 e 3 complete
- Struttura finale: `config.py`, `core/` (client, runner, parser, prompt_builder, web_search), `data/`, `app.py`
- Avviare con: `streamlit run app.py`
- Prossimo: testare l'app, poi implementare Fase 4 (web search)
