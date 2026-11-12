# CRITICAL RULES - MUST FOLLOW

## RESPONSES

- Keep responses concise and to the point - unless the user asks otherwise

## PLANNING MODE

- Always ask clarifying questions
- Never assume design, tech stack or features
- Use subagents to assist with research
- Use subagents to review the different aspects of your plan before presenting to the user

## CHANGE / EDIT MODE

- Never implement features yourself when possible - use subagents!
- Identify changes from the plan that can be implemented in parallel, and use subagents to implement the features efficiently
- When using subagents to implement features, act as a coordinator only
- Use the best model for the task - premium models for complex tasks (like coding) and mid-tier models for simpler tasks, like documentation
- After completing features (large or small), always run commands like `uv run ruff format` and `uv run ruff check --fix`  to fix code linter issues
- Include an "Issues" section on the summary of each task to report any obstacules you might have during the task and how did you solved them
- Use subagents to call MCP tools and run Github tasks, tests and code reviews

## TESTING
- Use pytest for testing your changes
- Never assume your changes simply work, always test with minimum 90% code coverage


## GOTCHAS
- If you need to Environment and setup instructions read them on @README.md


# Agent Instructions for the Repository

### Key Commands
- Investing Pro analysis: `uv run scan_investing_pro.py` (depends on chrome-debug CLI command in a separate terminal to extract site data using Playwright)
- TradingView analysis: `uv run scan_tradingview.py` (depends on chrome-debug CLI command in a separate terminal to extract site data using Playwright)

### Important Files
- Investing Pro analysis script: `scan_investing_pro.py`
- Trading view script: `scan_tradingview.py`
- Shared utilities: `common.py`
- Stocks Ticker symbols used by scripts: `symbols_buy_check.json`, `symbols_sell_check.json`, and `symbols_test.json`

### Workflow Notes
- Analysis outputs to console by default; use `--output json` for machine-readable results
