# Contexto Especializado do Domínio e Decisões

Este diretório armazena o conhecimento formalizado, as decisões arquiteturais duráveis e os precedentes catalogados do projeto **Daemon Tools**.

---

## 1. Estrutura do Contexto

O contexto persistido organiza-se em três pilares fundamentais:

```text
docs/context/
├── domain/        # Conhecimento reutilizável sobre o sistema de RPG Daemon/Trevas
├── decisions/     # Architectural Decision Records (ADRs) formais e permanentes
└── precedents/    # Casos concretos e decisões pontuais aprovadas em lotes anteriores
```

---

## 2. Descrição dos Pilares

### Domain (`docs/context/domain/`)
Contém o conhecimento formalizado sobre as regras, taxonomia e convenções do universo Daemon/Trevas:
- `taxonomy.md`: Catálogo completo de categorias canônicas do sistema.
- `entity-patterns.md`: Guia de diferenciação e modelagem de entidades (Aprimoramentos, Kits, Raças, Poderes, Magias, NPCs).
- `relation-types.md`: Vocabulário padronizado de relações semânticas entre entidades e regras.

### Decisions (`docs/context/decisions/`)
Registros formais de decisões de arquitetura (ADRs) que orientam o design do sistema, políticas de dados e governança de agentes. Qualquer nova diretriz arquitetural permanente deve ser documentada aqui.

### Precedents (`docs/context/precedents/`)
Registros de decisões editoriais tomadas sobre obras específicas em interações passadas.
> [!IMPORTANT]
> **Precedente Não Vira Regra Universal Automaticamente**: Casos anteriores servem como guia de consistência para o mesmo livro ou situações análogas, mas não sobrepõem as regras universais da Constituição ou os schemas formais do projeto.

---

## 3. Como os Agentes Devem Consumir Este Contexto

Os agentes nunca devem depender de memórias voláteis de chat. Toda a base de conhecimento necessária para interpretar e classificar o acervo Daemon deve ser extraída diretamente destes documentos versionados.
