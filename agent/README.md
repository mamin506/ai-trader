# Agent Documentation

This directory contains design documentation and architectural decisions for the AI Trader project. These documents serve as context for development and are automatically loaded by Claude Code.

## Document Index

### Core Architecture
- [architecture-overview.md](architecture-overview.md) - System architecture and module relationships
- [tech-stack.md](tech-stack.md) - Technology stack selections and rationale
- [development-plan.md](development-plan.md) - Project timeline, milestones, and progress tracking

### Layer Design
- [data-layer-design.md](data-layer-design.md) - Data acquisition and storage design
- [strategy-layer-design.md](strategy-layer-design.md) - Strategy development framework
- [portfolio-management-design.md](portfolio-management-design.md) - Portfolio allocation and rebalancing
- [risk-management-design.md](risk-management-design.md) - Risk control design
- [execution-layer-design.md](execution-layer-design.md) - Order execution system design

### Development Experience
- [user-interface-design.md](user-interface-design.md) - Python APIs, CLI tools, and Jupyter integration
- [development-guidelines.md](development-guidelines.md) - Coding standards and constraints

## Document Status

- ✅ README.md - Index file
- ✅ tech-stack.md - All technology stack decisions completed
- ✅ data-layer-design.md - Data provider abstraction design
- ✅ strategy-layer-design.md - Strategy framework, signal semantics, TA-Lib selection
- ✅ portfolio-management-design.md - Allocation algorithms, rebalancing, portfolio theory
- ✅ risk-management-design.md - Stop-loss, risk checks, QuantStats integration
- ✅ execution-layer-design.md - Order execution abstraction, paper trading, Alpaca integration
- ✅ architecture-overview.md - System architecture, data flow, interfaces
- ✅ development-plan.md - Project timeline, task breakdown, sprint tracking, milestones
- ✅ user-interface-design.md - Python APIs, CLI tools, Jupyter integration, visualization
- ✅ development-guidelines.md - Coding standards, project structure, diagram conventions

## How to Use

When starting a new Claude Code session, these documents are automatically included in the context, ensuring continuity of design decisions across sessions.

When making architectural changes:
1. Discuss the change thoroughly
2. Update the relevant document(s)
3. Update this README if new documents are added
