#!/usr/bin/env python3
"""
TradingView Automation Script
"""

import asyncio
from playwright.async_api import async_playwright
from common import send_telegram_message, load_symbols


async def check_tradingview_rating(page, symbol: str) -> tuple[bool, str, float, str]:
    """
    Check TradingView for a symbol's analyst rating and forecast upside
    Returns: (is_strong_buy_and_high_upside, rating, upside_percent)
    """
    try:
        # Go directly to symbol page (more reliable than search)
        url = f"https://www.tradingview.com/symbols/{symbol}/"
        print(f"Navigating to {url}")
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # Now we should be on the symbol's chart page
        # Click on the Forecast tab to access forecast-specific data
        try:
            forecast_tab = page.locator("text=Forecast").first
            if await forecast_tab.count() > 0:
                print(f"Clicking forecast tab for {symbol}")
                await forecast_tab.click()
                await page.wait_for_timeout(3000)  # Wait for the tab to load
                print(f"Forecast tab clicked for {symbol}")
            else:
                print(
                    f"Forecast tab not found for {symbol}, trying to extract from main page"
                )
                # We'll try to extract from the main page as a fallback
        except Exception as e:
            print(f"Error clicking forecast tab for {symbol}: {e}")
            # Continue to try to extract from the main page

        # Extract analyst rating, price target, and upside from the forecast tab area
        rating = ""
        upside = 0.0
        price_target = ""
        price_change = ""
        percent_change = ""

        try:
            # Wait for forecast tab content to load
            await page.wait_for_timeout(3000)
            price_container = page.locator('[class*="detailsPriceWrap-"]')

            if await price_container.count() > 0:
                price_target = await price_container.locator(
                    '[data-qa-id="value"]'
                ).text_content()
                price_change = await price_container.locator(
                    '[class*="changeWrap-"] > span'
                ).first.text_content()
                percent_change = (
                    await price_container.locator('[class*="changeWrap-"] > span')
                    .filter(has_text="%")
                    .text_content()
                )
                upside = float(percent_change.replace("%", ""))

            strong_buy_locator = page.locator(
                '[class*="speedometerText-"]', has_text="Strong buy"
            )
            if await strong_buy_locator.count() > 0:
                opacity = await strong_buy_locator.evaluate(
                    "el => window.getComputedStyle(el).opacity"
                )
                if float(opacity) > 0:
                    rating = "Strong buy"

        except Exception as e:
            print(f"Error extracting forecast data for {symbol}: {e}")

        # Check if criteria are met
        is_strong_buy = "strong buy" in rating.lower() if rating else False
        high_upside = upside > 30.0

        print(
            f"{symbol}: Rating='{rating}', Upside={upside}%, Price Target={price_target}, Strong Buy={is_strong_buy}, High Upside={high_upside}, Price Change={price_change}"
        )

        return (is_strong_buy and high_upside, rating, upside, price_change)

    except Exception as e:
        print(f"Error processing symbol {symbol}: {e}")
        return (False, "", 0.0, "")


async def main():
    """Main automation function"""
    print("Starting TradingView automation...")

    # Load symbols
    symbols = load_symbols()
    if not symbols:
        print("No symbols loaded. Exiting.")
        return

    print(f"Loaded {len(symbols)} symbols: {symbols}")

    # Process each symbol
    results = []

    # Use Playwright
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)  # Set to True for headless
        context = await browser.new_context()
        page = await context.new_page()

        # Now process symbols
        try:
            for symbol in symbols:
                print(f"\nProcessing {symbol}...")
                try:
                    (
                        is_match,
                        rating,
                        upside,
                        price_change,
                    ) = await check_tradingview_rating(page, symbol)
                    if is_match:
                        results.append(
                            {
                                "symbol": symbol,
                                "rating": rating,
                                "upside": upside,
                                "price_change": price_change,
                            }
                        )
                        print(f"✓ {symbol} matches criteria!")
                    else:
                        print(f"✗ {symbol} does not match criteria")
                except Exception as e:
                    print(f"Error processing {symbol}: {e}")

                # Add delay between symbols to avoid rate limiting
                await page.wait_for_timeout(3000)
        finally:
            await browser.close()

        # Prepare and send results
        if results:
            message = "<b>TradingView Strong Buy Alerts</b>\n\n"
            message += "Symbols with 'Strong buy' rating and >30% upside:\n\n"

            for result in results:
                message += f"• <b>{result['symbol']}</b>\n"
                message += f"  Rating: {result['rating']}\n"
                message += f"  Upside: {result['upside']}%\n"
                message += f"  Price Change: {result['price_change']}\n\n"

            message += f"Total: {len(results)} symbols found"

            print("\nSending results to Telegram...")
            success = await send_telegram_message(message)
            if success:
                print("Results sent successfully!")
            else:
                print("Failed to send results to Telegram")

            # Also print results to console
            print("\n" + "=" * 50)
            print("RESULTS:")
            print("=" * 50)
            for result in results:
                print(
                    f"{result['symbol']}: {result['rating']} ({result['upside']}% upside)"
                )
            print("=" * 50)
        else:
            print("No symbols matched the criteria.")
            message = "<b>TradingView Strong Buy Alerts</b>\n\nNo symbols found with 'Strong buy' rating and >30% upside."
            await send_telegram_message(message)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
