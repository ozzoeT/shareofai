# Piano di evoluzione verso un prodotto vendibile — Share of AI

Roadmap in fasi, pensata per trasformare il prototipo in un prodotto SaaS vendibile
nello spazio "AI visibility / Share of Voice negli LLM". Ogni fase è autoconclusiva
(porta valore vendibile da sola) e costruisce sulla precedente.

---

## Fase 0 — Solidità tecnica (prerequisito)
**Obiettivo:** rendere il prototipo affidabile prima di costruirci sopra un business.

- Validazione credenziali (Apollo, Tavily) con messaggi chiari
- Fix schema mismatch `source_evaluation` (parser ↔ system prompt)
- Autosave robusto (path persistente, errori non silenziati)
- Test automatici minimi su `core/` (parser, brand_groups, web_search) + CI

**Perché prima:** ogni fase successiva aggiunge automazione (run schedulate, multi-tenant);
bug nascosti oggi diventano incidenti silenziosi domani su dati di clienti reali.

**Effort:** 1 sessione dedicata.

---

## Fase 1 — Da "fotografia" a "monitoraggio"
**Obiettivo:** trasformare il tool da analisi one-shot a tracking nel tempo — è ciò che
giustifica un abbonamento ricorrente invece di una consulenza spot.

### Decisioni architetturali (deep dive 2026-06-11)

- **Storage**: SQLite, `data/history.db` (gitignored). Due tabelle:
  - `runs`: id, timestamp, label opzionale, modelli usati, hash del prompt set
  - `results`: run_id (FK), model, prompt_index, tone, language, category,
    `preferred_brand` **grezzo** (non normalizzato), confidence, decision,
    campi `source_evaluation`, web_search_used
- **Normalizzazione a query-time, non a salvataggio**: il brand grezzo è salvato
  così com'è; la mappatura verso i brand group viene applicata al momento di
  disegnare i grafici, usando i brand groups *correnti*. Così se l'utente
  rinomina/aggrega un brand oggi, lo storico si aggiorna subito senza migrazioni.
- **"Share of AI nel tempo"**: per ogni run, % di prompt in cui ogni brand
  (normalizzato) è `preferred_brand`, filtrabile per tono/modello/categoria.
  Grafico a linee: x = timestamp run, y = %, una linea per brand.
- **Flusso utente**: bottone "💾 Salva nello storico" dopo una run (o da JSON
  caricato) → insert in SQLite. Nuovo tab "📈 Storico" con tabella run passate
  + grafico trend. L'export JSON esistente resta come backup/portabilità.

### Sotto-fasi

- **1a** (1 sessione): SQLite + salvataggio run + tab Storico con tabella run
  passate e grafico trend base ("Share of AI" per brand nel tempo, senza filtri)
- **1b** (1 sessione): filtri avanzati sul trend (tono/categoria/modello) +
  confronto run-vs-run con diff
- **1c** (1 sessione): run schedulate (settimanali, riusano streaming +
  autosave già implementati) + alert base ("Brand X: -12pp nel tono
  'technical' rispetto alla run precedente")

**Valore vendibile:** "monitora la tua presenza nell'AI nel tempo, non solo oggi" —
il pitch principale di un abbonamento mensile. Già la 1a da sola è dimostrabile
a un cliente.

**Effort:** 3 sessioni (1a + 1b + 1c).

---

## Fase 2 — Dal dato al deliverable
**Obiettivo:** il cliente non vuole una dashboard, vuole un report che gli dica cosa fare.

- **Report esportabile brandizzato** (PDF/HTML): combina i tab esistenti
  (brand preference, tono, source evaluation, content analysis) in un documento
  unico con logo/cliente
- **Raccomandazioni azionabili**: sezione "cosa fare" generata dall'LLM a partire dai
  digest `source_evaluation` — es. "le tue fonti sono deboli su review, i competitor
  vincono con contenuto clinico → produrre X contenuti di tipo Y"
- **Confronto competitivo diretto**: report "tu vs. competitor X" con gap analysis

**Valore vendibile:** deliverable tangibile da mostrare a un cliente non tecnico
(marketing manager) — è quello che si "vende" davvero, non l'accesso al tool.

**Effort:** 2 sessioni (template report + prompt di sintesi raccomandazioni).

---

## Fase 3 — Multi-tenant e parametrizzazione del dominio
**Obiettivo:** passare da "un prototipo per il veterinario" a "un prodotto per qualsiasi
settore consumer".

- **Workspace per cliente**: ogni cliente ha il proprio set di brand groups, prompt
  library, system prompt di dominio, storico run — isolamento dati
- **System prompt parametrico**: il dominio (veterinario, oggi cablato in
  `data/system_prompt.txt`) diventa un parametro di configurazione per workspace
- **Onboarding self-service**: wizard per configurare brand da monitorare,
  competitor, toni rilevanti, categorie prodotto

**Valore vendibile:** prodotto orizzontale → mercato enormemente più grande,
mantenendo il vertical pet/health care come case study di lancio.

**Effort:** 3-4 sessioni (refactor architetturale più consistente).

---

## Fase 4 — Differenziazione e retention
**Obiettivo:** feature che alzano il valore percepito e rendono il prodotto "appiccicoso".

- **Alert competitivi avanzati**: "il competitor X ti ha superato nel tono 'technical'
  questa settimana"
- **Benchmark di settore**: dati aggregati anonimizzati cross-cliente ("la media del
  tuo settore è...")
- **Integrazione con content workflow**: collegare le raccomandazioni del Source
  Evaluation a un CMS/Trello per tracciare le azioni intraprese
- **API/embed**: esporre i dati via API per integrazione in dashboard esistenti del cliente

**Valore vendibile:** da "tool" a "piattaforma" — aumenta lock-in e prezzo medio.

**Effort:** ongoing, da prioritizzare in base al feedback dei primi clienti.

---

## Sequenza consigliata e razionale

```
Fase 0 (solidità) → Fase 1 (monitoraggio) → Fase 2 (report) → pilota con 1-2 clienti
                                                                      ↓
                                              Fase 3 (multi-tenant) ← feedback pilota
                                                                      ↓
                                                                  Fase 4 (retention)
```

**Perché questo ordine:**
- Fase 0+1+2 sono fattibili mantenendo il dominio veterinario attuale → si arriva a un
  **pilota vendibile entro ~5-6 sessioni**, senza il costo del refactor multi-tenant
- Il refactor multi-tenant (Fase 3) ha senso *dopo* aver validato con clienti reali
  cosa serve davvero — evita di generalizzare prematuramente
- Fase 4 è guidata dal feedback, non pianificabile in dettaglio ora

## Note su pricing (da validare con i primi clienti)

- Tier per: numero di brand monitorati × numero di modelli LLM × frequenza run
- Il deliverable di Fase 2 (report) è probabilmente l'unità di valore più facile da
  far percepire a un buyer non tecnico — considerare anche un modello "report on demand"
  oltre all'abbonamento per il monitoraggio continuo
