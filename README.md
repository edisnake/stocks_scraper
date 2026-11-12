# Stocks Scraper

Reviews stocks from defined websites (currently investing.com and tradingview.com but willing to extend it to other sources). 
The scripts gather financial indicators from different stocks to analyze and identify strong buy and sell signals and then send them as notifications to the defined telegram chat id on the *.env* file

## ENVIRONMENT & SETUP
- Requires `Python >=3.12` and `uv` installed on your env
- Run `uv sync` to install project dependencies, which will be installed on the *.venv* folder
- Use `uv` for script execution
- Use `uv add [package_name]` for addig new dependencies

### Playwright SETUP

Playwright MCP configuration is in `.mcp.json`

**The scripts need a Google Chrome debug session to run, e.g:**
#### Command to add an alias on your CLI env

```
nano ~/.zshrc
```

Then add the following text on the editor and save it, so you can reuse it easily as a _chrome-debug_ command

```
alias chrome-debug='/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/ChromeProfiles/investing_pro_debug"'
```

## Run Commands
**Following commands depend on the chrome-debug CLI command in a separate terminal to extract site data using Playwright**
- Investing Pro analysis: `uv run scan_investing_pro.py` 
- TradingView analysis: `uv run scan_tradingview.py`