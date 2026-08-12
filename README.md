# Radar — agente de descoberta de vagas

Sistema pessoal e autônomo que varre os ATS de empresas selecionadas, avalia
cada vaga sob a perspectiva de um recrutador (score duplo: fit do candidato
+ probabilidade de shortlist) e organiza os resultados. **Nunca se candidata
automaticamente** — decisão e envio continuam sendo atos humanos, fora do
sistema. Especificação completa em [`PRD Radar v2.0`](#) (não versionado
neste repo).

## Escopo desta versão

Implementa as **Fases 0-2** do roadmap do PRD:

- **Fase 0 — Perfil canônico**: [`perfil.json`](./perfil.json), normalizado a
  partir do export do LinkedIn.
- **Fase 1 — Radar autônomo**: watchlist de empresas, conectores de ATS
  (Greenhouse, Lever, Ashby, Gupy), diff/dedup de vagas, 4 rodadas via Celery
  Beat, `run_log`, notificação por Telegram.
- **Fase 2 — Inteligência**: reconstrução de brief do recrutador, detecção
  de knockouts, score duplo (`score` / `recruiter_score`), boolean string
  reversa, sincronização com Google Sheets.

**Fora de escopo** (fases posteriores do PRD, não implementadas aqui):
geração de CV/carta, parsing de ATS simulado, triagem em dois passes, gate
de qualidade, estrutura de dossiê e Google Drive (Fase 3); heartbeat/DLQ
avançados e painel de rodadas (Fase 4); autocalibração de horários (Fase 5);
vitrine inbound / auditoria de LinkedIn (Fase 1.5).

## Arquitetura

```
radar/
├── connectors/     # Greenhouse, Lever, Ashby, Gupy — fetch_jobs(company) -> list[RawJob]
├── services/        # diff, dedup, promoção de tier, sync com Google Sheets
├── notifications/   # Telegram Bot API
├── intelligence/     # llm_client (Anthropic) + brief/knockouts/scoring/boolean_string
├── models.py         # Company, Job, RunLog
└── tasks.py           # executar_rodada — orquestração de uma rodada completa
```

A cada rodada (`radar.tasks.executar_rodada`): poll paralelo dos ATS → diff
→ dedup → (por vaga nova) brief → knockouts → score duplo → boolean string
(se aprovada) → notificação Telegram → sync Google Sheets → fecha
`run_log`. Detalhes e requisitos funcionais referenciados em comentários no
próprio código (`RF-XX`).

## Configuração

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # preencha as credenciais reais
python manage.py migrate
```

Variáveis de ambiente (`.env`, ver `.env.example`):

| Variável | Uso |
|---|---|
| `DATABASE_URL` | Postgres em produção; sem ela, cai em SQLite local |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis |
| `ANTHROPIC_API_KEY` | Chamadas de inteligência (Haiku/Sonnet) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Notificação pós-rodada |
| `GOOGLE_SHEETS_CREDENTIALS_PATH` / `GOOGLE_SHEETS_SPREADSHEET_ID` | Sync da planilha |

Sem essas credenciais configuradas, os módulos correspondentes
(`notifications/telegram.py`, `services/sheets_sync.py`) logam e não fazem
nada — uma rodada roda normalmente sem notificar nem sincronizar planilha.

### Rodando as 4 rodadas autônomas

```bash
celery -A radarvagas worker -l info
celery -A radarvagas beat -l info
```

O agendamento (R1 06h/R2 10h/R3 14h/R4 18h30, horário de Brasília) está em
`radarvagas/celery.py`, espelhando o Anexo G do PRD. R1 roda todo dia; nela,
`radar.tasks.determine_mode` decide em tempo real se é modo `backlog`
(segunda-feira) ou `reduzido` (fim de semana) — não há schedules separados
para isso.

### Conectores de ATS

`Company.ats_board_url` guarda o identificador (ou URL completa) do board no
ATS:

- **Greenhouse**: token do board ou `https://boards.greenhouse.io/{token}`
- **Lever**: site do board ou `https://jobs.lever.co/{site}`
- **Ashby**: nome do board ou `https://jobs.ashbyhq.com/{nome}`
- **Gupy**: URL completa do endpoint de listagem do tenant (a Gupy não
  publica uma API pública estável e documentada como as demais — valide o
  endpoint real da empresa-alvo antes de usar em produção; ver comentário em
  `radar/connectors/gupy.py`)

## Testes

```bash
pytest
```

29 testes cobrindo: parsing de cada conector contra fixtures de payload real
(`radar/tests/fixtures/`), retry/backoff, diff/dedup, `perfil.json`
(integridade e ausência de dados fabricados), a camada de inteligência com o
`llm_client` mockado (sem chamar a API Anthropic de verdade) e o pipeline
completo de `executar_rodada` (caminho feliz + isolamento de falha de uma
fonte).

## Limitações conhecidas

- Sem Postgres/Redis/credenciais reais neste ambiente de desenvolvimento
  inicial — o pipeline foi validado via testes automatizados com
  fixtures/mocks, não em execução ao vivo. Configure as variáveis acima e
  rode `celery beat` + `celery worker` num ambiente com essa infra para
  operar de fato.
- O conector Gupy assume um endpoint por tenant que precisa ser validado
  manualmente (ver acima).
- `perfil.json` tem `preferencias` (faixa salarial, localidades, modelo de
  trabalho aceito, dealbreakers) vazias — edite o arquivo antes de usar o
  Radar para valer (RF-01.5: é um arquivo git-editável, não há UI).
