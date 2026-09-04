# ADR-0003 — Development Fork and Upstream Release Model

## Status

Accepted

## Context

O desenvolvimento inicial do Daemon Tools é realizado principalmente neste PC por meio do Antigravity + Gemini 3.7 High.

A conta SaruAkaza possui o ambiente de desenvolvimento, enquanto `guraassessoria/daemon` é o repositório oficial do projeto.

Queremos poder experimentar, implementar e validar mudanças sem utilizar o repositório oficial como ambiente de desenvolvimento direto.

## Decision

O repositório:

`SaruAkaza/daemon`

será utilizado como repositório remoto de desenvolvimento (`origin`).

O repositório:

`guraassessoria/daemon`

será utilizado como repositório oficial (`upstream`).

Todo desenvolvimento deverá passar primeiro por:

1. implementação local;
2. testes locais;
3. commit em branch;
4. push para `origin`;
5. revisão;
6. somente então integração deliberada com `upstream`.

Alterações não devem ser enviadas automaticamente ao upstream.

## Consequences

### Positive

- desenvolvimento isolado do repositório oficial;
- backup remoto dos trabalhos do Antigravity;
- possibilidade de testar livremente;
- histórico claro entre desenvolvimento e versão oficial;
- integração futura por Pull Request.

### Trade-offs

- será necessário manter o fork sincronizado com upstream;
- alterações oficiais devem ser trazidas regularmente para o ambiente de desenvolvimento;
- integração com Gurass exigirá etapa explícita de revisão.

## Development rule

Nada será enviado para `guraassessoria/daemon` sem passar pelos gates locais definidos em `docs/architecture/pipeline.md`.

## Current executor

O executor principal nesta fase é Antigravity + Gemini 3.7 High.

Esta decisão não torna a arquitetura dependente do Gemini ou do Antigravity.

## Supersedes

None
