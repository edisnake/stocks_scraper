#!/usr/bin/env python3

import asyncio
import traceback
import time
from playwright.async_api import async_playwright
from common import (
    send_telegram_message,
    load_symbols,
    load_portfolio_symbols,
    PROCESS_SELL_SIGNALS,
)
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

exclude_candidates = []
rating_map = {"excellent": 5, "great": 4, "good": 3, "fair": 2, "poor": 1}


async def _get_float(page, selector: str) -> float:
    try:
        return float(
            (await page.locator(selector).first.inner_text())
            .replace("x", "")
            .replace("%", "")
        )
    except ValueError as e:
        print(f"Error extracting {selector}: {e}")
        return 0


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(3),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def check_investingpro_buy_rating(
    page, symbol: str
) -> tuple[bool, str, float, float, float, float, float, float, float, float]:
    """
    Check Investing Pro for a symbol's analyst rating and forecast upside
    Returns: (is_strong_buy_and_high_upside, rating, target_upside, price_change, current_price, current_upside, uncertainty_level, consensus, pe_ratio, roic, roce)
    """
    try:
        # Go directly to symbol page (more reliable than search)
        url = f"https://www.investing.com/pro/{symbol}"
        print(f"Navigating to {url}")
        await page.goto(url, wait_until="networkidle")

        # Extract analyst rating, price target, and upside from the forecast tab area
        rating = ""
        current_upside = 0.0
        target_upside = None
        average_target = None
        price_change = None
        current_price = 0.0
        uncertainty_level = ""
        consensus = None
        pe_ratio = None
        roic = None
        roce = None
        low_pe_ratio_msg = (
            "Trading at a low P/E ratio"  # "relative to near-term earnings growth"
        )

        try:
            # Wait for the page to load
            await page.wait_for_timeout(3000)

            health_indicator = page.locator(
                '[data-rbd-draggable-id="Financial Health"]'
            ).get_by_text("Performance")

            if await health_indicator.count() > 0:
                # Locate the cell that follows the one containing the text
                consensus = await _get_float(
                    page, "td:has-text('Consensus Recommendation') + td"
                )
                pe_ratio = await _get_float(page, "td:has-text('P/E Ratio') + td")
                roic = await _get_float(
                    page, "td:has-text('Return on Invested Capital') + td"
                )
                roce = await _get_float(
                    page, "td:has-text('Return on Capital Employed') + td"
                )

                rating = (
                    (await health_indicator.text_content()).strip().split()[0].lower()
                )

            upside_container = page.get_by_text("Upside", exact=True).locator("..")

            if await upside_container.count() > 0:
                print("Upside container found...")
                current_price_container = page.get_by_text("Price", exact=True).locator(
                    ".."
                )
                current_price = (
                    await current_price_container.locator("div").nth(1).text_content()
                )
                current_price = float(
                    current_price.replace("USD", "").replace(",", "").strip()
                )

                # Upside
                upside_percentage = (
                    await upside_container.locator("div").nth(1).text_content()
                )

                # Uncertainty
                uncertainty_container = page.get_by_text(
                    "Uncertainty", exact=True
                ).locator("..")
                uncertainty_level = (
                    await uncertainty_container.locator("div").nth(1).text_content()
                ).lower()

                current_upside = float(upside_percentage.replace("%", ""))
                if target_upside := await _get_float(
                    page, "td:has-text('Upside (Analyst Target)') + td"
                ):
                    price_change = round(current_price * (target_upside / 100), 2)
                    average_target = round(current_price + price_change, 2)
                else:
                    print(
                        f"There's no Upside (Analyst Target) data for symbol {symbol}..."
                    )

                if target_upside:
                    if (
                        rating in ("good", "great", "excellent")
                        and uncertainty_level in ("low", "med")
                        and current_upside >= 18
                        and 1 <= consensus < 2
                        and (
                            pe_ratio <= 25
                            or (await page.get_by_text(low_pe_ratio_msg).count() > 0)
                        )
                        and (roic >= 10 and roce >= 10)
                        and (roic >= 13 or roce >= 13)
                    ):
                        rating = "Strong buy"
                    elif (
                        rating == "high"
                        or roic < 8
                        or roce < 8
                        or rating == "poor"
                        or consensus > 3.5
                        or (target_upside < current_upside and target_upside < 13)
                    ):
                        exclude_candidates.append(
                            {
                                "symbol": symbol,
                                "rating": rating,
                                "roic": roic,
                                "roce": roce,
                                "consensus": consensus,
                                "target_upside": target_upside,
                                "current_upside": current_upside,
                                "pe_ratio": pe_ratio,
                            }
                        )
                        print(f"Symbol {symbol} is candidate for exclusion.")
            else:
                print("Upside container Not Found...")
                exclude_candidates.append(
                    {
                        "symbol": symbol,
                        "rating": rating,
                        "roic": roic,
                        "roce": roce,
                        "consensus": consensus,
                        "target_upside": target_upside,
                        "current_upside": current_upside,
                        "pe_ratio": pe_ratio,
                    }
                )
                print(f"Symbol {symbol} is candidate for exclusion.")

        except Exception:
            print(f"Error extracting data for {symbol}:")
            print(traceback.format_exc())
            raise Exception(f"Error extracting data for {symbol}")

        # Check if criteria are met
        is_strong_buy = "strong buy" in rating.lower() if rating else False
        high_upside = target_upside >= 25 if target_upside else False

        if target_upside:
            print(
                f"{symbol}: \n"
                f"  Rating: {rating.title()}\n"
                f"  Target Upside: {target_upside}%\n"
                f"  Target Price: {average_target}\n"
                f"  Strong Buy: {is_strong_buy}\n"
                f"  High Upside: {high_upside}\n"
                f"  Current upside: {current_upside}\n"
                f"  Current Price: {current_price}\n"
                f"  Uncertainty: {uncertainty_level}\n"
                f"  Price Change: {price_change}\n"
                f"  Consensus Recommendation: {consensus}\n"
                f"  P/E Ratio: {pe_ratio}\n"
                f"  ROIC: {roic}\n"
                f"  ROCE: {roce}\n"
            )

        return (
            is_strong_buy and high_upside,
            rating,
            target_upside,
            price_change,
            current_price,
            current_upside,
            uncertainty_level,
            consensus,
            pe_ratio,
            roic,
            roce,
        )

    except Exception as e:
        raise Exception(f"Error processing symbol {symbol}: {e}")


async def fetch_buy_symbol(page, symbol, results):
    print(f"\nProcessing {symbol}...")
    try:
        (
            is_match,
            rating,
            target_upside,
            price_change,
            current_price,
            current_upside,
            uncertainty,
            consensus,
            pe_ratio,
            roic,
            roce,
        ) = await check_investingpro_buy_rating(page, symbol)
        if is_match:
            results.append(
                {
                    "symbol": symbol,
                    "rating": rating,
                    "target_upside": target_upside,
                    "price_change": price_change,
                    "current_price": current_price,
                    "current_upside": current_upside,
                    "uncertainty": uncertainty,
                    "consensus": consensus,
                    "pe_ratio": pe_ratio,
                    "roic": roic,
                    "roce": roce,
                }
            )
            print(f"  ✓ {symbol} matches criteria!")
        else:
            print(f"  ✗ {symbol} does not match criteria")
    except Exception as e:
        raise e


async def check_investingpro_sell_rating(
    page, symbol: str
) -> tuple[bool, str, float, float, float, float, str, float, float]:
    """
    Check Investing Pro for a symbol's sell signals
    Returns: (is_sell_signal, rating, target_upside, price_change, current_price, current_upside, uncertainty, consensus, pe_ratio)
    """
    try:
        # Go directly to symbol page (more reliable than search)
        url = f"https://www.investing.com/pro/{symbol}"
        print(f"Navigating to {url}")
        await page.goto(url, wait_until="networkidle")

        # Extract analyst rating, price target, and upside from the forecast tab area
        rating = ""
        current_downside = 0.0
        target_downside = None
        average_target = None
        price_change = None
        current_price = 0.0
        uncertainty_level = ""
        consensus = None
        pe_ratio = None
        high_pe_ratio_msg = (
            "Trading at a high P/E ratio"  # "relative to near-term earnings growth"
        )

        try:
            # Wait for the page to load
            await page.wait_for_timeout(3000)

            downside_container = page.get_by_text("Downside", exact=True).locator("..")

            if await downside_container.count() > 0:
                print("Downside container found...")
                current_price_container = page.get_by_text("Price", exact=True).locator(
                    ".."
                )
                current_price = (
                    await current_price_container.locator("div").nth(1).text_content()
                )
                current_price = float(
                    current_price.replace("USD", "").replace(",", "").strip()
                )

                downside_percentage = (
                    await downside_container.locator("div").nth(1).text_content()
                )

                uncertainty_container = page.get_by_text(
                    "Uncertainty", exact=True
                ).locator("..")
                uncertainty_level = (
                    await uncertainty_container.locator("div").nth(1).text_content()
                ).lower()

                current_downside = float(downside_percentage.replace("%", ""))
                average_target = (
                    await page.get_by_text("Analyst Targets", exact=True)
                    .locator("..")
                    .locator("div")
                    .last.text_content()
                )
                average_target = float(average_target.replace("$", "").replace(",", ""))
                price_change = round(average_target - current_price, 2)
                target_downside = round((price_change / current_price) * 100, 2)

                health_indicator = page.locator(
                    '[data-rbd-draggable-id="Financial Health"]'
                ).get_by_text("Performance")
                if await health_indicator.count() > 0:
                    # Locate the cell that follows the one containing the text
                    consensus = float(
                        await page.locator(
                            "td:has-text('Consensus Recommendation') + td"
                        ).inner_text()
                    )
                    pe_ratio = float(
                        (
                            await page.locator(
                                "td:has-text('P/E Ratio') + td"
                            ).first.inner_text()
                        ).replace("x", "")
                    )

                    rating = (
                        (await health_indicator.text_content())
                        .strip()
                        .split()[0]
                        .lower()
                    )

                    # Sell signal criteria:
                    # - Rating in ("weak", "fair", "poor")
                    # - Uncertainty in ("low", "med")
                    # - Current downside <= -15% (downside)
                    # - Consensus recommendation >= 3.5 (Sell/Strong Sell)
                    # - Target downside <= -25% (significant downside target)
                    # - P/E ratio > 35 (overvalued)
                    if (
                        rating in ("weak", "fair", "poor")
                        and uncertainty_level in ("low", "med", "high")
                        and current_downside <= -15
                        and consensus >= 3.5
                        and target_downside <= -20
                        and (
                            pe_ratio >= 35
                            or (await page.get_by_text(high_pe_ratio_msg).count() > 0)
                        )
                    ):
                        rating = "Strong sell"
            else:
                print("Downside container Not Found...")

        except Exception:
            print(f"Error extracting data for {symbol}:")
            print(traceback.format_exc())

        # Check if criteria are met
        is_sell_signal = rating == "Strong sell"

        if target_downside is not None:
            print(
                f"{symbol}: \n"
                f"  Rating: {rating.title()}\n"
                f"  Target Downside: {target_downside}%\n"
                f"  Target Price: {average_target}\n"
                f"  Strong Sell: {is_sell_signal}\n"
                f"  Current Downside: {current_downside}\n"
                f"  Current Price: {current_price}\n"
                f"  Uncertainty: {uncertainty_level}\n"
                f"  Price Change: {price_change}\n"
                f"  Consensus Recommendation: {consensus}\n"
                f"  P/E Ratio: {pe_ratio}\n"
            )

        return (
            is_sell_signal,
            rating,
            target_downside,
            price_change,
            current_price,
            current_downside,
            uncertainty_level,
            consensus,
            pe_ratio,
        )

    except Exception as e:
        print(f"Error processing symbol {symbol}: {e}")
        return (False, "", 0.0, 0.0, 0.0, 0.0, "", 0.0, 0.0)


async def fetch_sell_symbol(page, symbol, results):
    print(f"\nProcessing {symbol} for sell signals...")
    try:
        (
            is_match,
            rating,
            target_upside,
            price_change,
            current_price,
            current_upside,
            uncertainty,
            consensus,
            pe_ratio,
        ) = await check_investingpro_sell_rating(page, symbol)
        if is_match:
            results.append(
                {
                    "symbol": symbol,
                    "rating": rating,
                    "target_upside": target_upside,
                    "price_change": price_change,
                    "current_price": current_price,
                    "current_upside": current_upside,
                    "uncertainty": uncertainty,
                    "consensus": consensus,
                    "pe_ratio": pe_ratio,
                }
            )
            print(f"  ✓ {symbol} matches SELL criteria!")
        else:
            print(f"  ✗ {symbol} does not match SELL criteria")
    except Exception as e:
        print(f"Error processing {symbol} for sell signals: {e}")


async def main():
    start_time = time.time()

    # Load symbols for buy signals
    buy_symbols = load_symbols()
    if not buy_symbols:
        print("No buy symbols loaded. Exiting.")
        return

    uncertainty_map = {
        "low": 1,
        "med": 2,
    }

    async with async_playwright() as p:
        print("Connecting to your active Chrome session...")
        try:
            # Connect directly to the browser you opened in Step 1
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception:
            print("\n❌ Error: Could not connect to Chrome.")
            print(
                "Make sure you closed Chrome completely and relaunched it via terminal using port 9222."
            )
            exit(1)

        # Grab the existing browser context and page
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()
        failed = False

        # Process buy symbols
        buy_results = []
        print("\n====== Processing BUY signals ======")
        print(f"Loaded {len(buy_symbols)} buy symbols: {buy_symbols}\n\n")
        try:
            for symbol in buy_symbols:
                await fetch_buy_symbol(page, symbol, buy_results)

            # Add delay between symbols to avoid rate limiting
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(e)
            failed = True
        finally:
            await browser.close()

        if exclude_candidates:
            exclude_candidates_sorted = sorted(
                exclude_candidates,
                key=lambda y: (
                    rating_map.get(y["rating"], 0),
                    y["roic"] or 0,
                    y["roce"] or 0,
                    -(y["consensus"] or 5),
                    -(y["pe_ratio"] or 99),
                    y["target_upside"] or -10,
                    y["current_upside"] or -10,
                ),
            )
            print(
                f"\n {len(exclude_candidates)} posible symbols found for exclusion from BUY signals in upcoming runs."
            )
            for exc_sym in exclude_candidates_sorted:
                print(f" - {exc_sym}")

        # Prepare and send results
        telegram_message = []

        # Process buy results
        if buy_results and not failed:
            buy_results = sorted(
                buy_results,
                key=lambda x: (
                    uncertainty_map.get(x["uncertainty"], 9),
                    -x["target_upside"],
                    -x["current_upside"],
                ),
            )
            buy_message = "<b>Investing Pro Strong BUY Alerts</b>\n\n"
            buy_message += "Symbols with 'Strong buy' rating upside:\n\n"
            current_uncertainty = ""

            for result in buy_results:
                if current_uncertainty != result["uncertainty"]:
                    buy_message += "-" * 25 + "\n"
                    current_uncertainty = result["uncertainty"]
                    buy_message += f"Uncertainty: {current_uncertainty.title()}\n\n"

                buy_message += f" • <b>{result['symbol']}</b>\n"
                buy_message += f"   Current Price: {result['current_price']}\n"
                buy_message += f"   Current Upside: {result['current_upside']}%\n"
                buy_message += f"   Target Upside: <b>{result['target_upside']}%</b>\n"
                buy_message += f"   Price Change: {result['price_change']}\n"
                buy_message += f"   Consensus: {result['consensus']}\n"
                buy_message += f"   P/E Ratio: {result['pe_ratio']}x\n"
                buy_message += f"   ROIC: {result['roic']}%\n"
                buy_message += f"   ROCE: {result['roce']}%\n\n"

            buy_message += f"Total BUY signals: {len(buy_results)} symbols found"
            telegram_message.append(buy_message)

            # Also print buy results to console
            print("\n" + "=" * 80)
            print(" BUY RESULTS:")
            print("=" * 80)
            for result in buy_results:
                print(
                    f"{result['symbol']}: {result['rating']} ({result['target_upside']}% target_upside) ({result['current_upside']}% current_upside)"
                )
            print("=" * 80)
        else:
            print("\n\n*** No BUY symbols matched the criteria. ***")
            buy_message = "<b>Investing Pro Strong BUY Alerts</b>\n\nNo symbols found with 'Strong buy' rating."
            telegram_message.append(buy_message)

        await process_sell_signals(uncertainty_map, telegram_message)

        # Combine all messages
        final_message = "\n\n".join(telegram_message)

        if not failed:
            print("\nSending results to Telegram...")
            success = await send_telegram_message(final_message)
            if success:
                print("Results sent successfully!")
            elif success is False:
                print("Failed to send results to Telegram")

        # Calculate and display elapsed time
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        print(f"\nAutomation task completed in {minutes:02d}m : {seconds:02d}s")


async def process_sell_signals(uncertainty_map, telegram_message):
    if not PROCESS_SELL_SIGNALS:
        print("PROCESS_SELL_SIGNALS is False - Skipping process_sell_signals...")
        return None

    # Load symbols for sell signals
    sell_symbols = load_portfolio_symbols()
    if not sell_symbols:
        print("No sell symbols loaded. Continuing with buy signals only.")

    # Process sell symbols
    sell_results = []
    print("\n\n====== Processing SELL signals ======")
    print(f"\nLoaded {len(sell_symbols)} sell symbols: {sell_symbols}\n\n")
    async with async_playwright() as p:
        try:
            # Connect directly to the browser you opened in Step 1
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception:
            print("\n❌ Error: Could not connect to Chrome.")
            print(
                "Make sure you closed Chrome completely and relaunched it via terminal using port 9222."
            )
            exit(1)

        # Grab the existing browser context and page
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            for symbol in sell_symbols:
                await fetch_sell_symbol(page, symbol, sell_results)

            # Add delay between symbols to avoid rate limiting
            await page.wait_for_timeout(3000)
        finally:
            await browser.close()

        # Process sell results
        if sell_results:
            sell_results = sorted(
                sell_results,
                key=lambda x: (
                    uncertainty_map.get(x["uncertainty"], 9),
                    x["target_upside"],  # Ascending for sell signals (worst first)
                ),
            )
            sell_message = "<b>Investing Pro Strong SELL Alerts</b>\n\n"
            sell_message += "Symbols with 'Strong sell' rating:\n\n"
            current_uncertainty = ""

            for result in sell_results:
                if current_uncertainty != result["uncertainty"]:
                    sell_message += "-" * 25 + "\n"
                    current_uncertainty = result["uncertainty"]
                    sell_message += f"Uncertainty: {current_uncertainty.title()}\n\n"

                sell_message += f" • <b>{result['symbol']}</b>\n"
                sell_message += f"   Current Price: {result['current_price']}\n"
                sell_message += f"   Current Downside: {result['current_upside']}%\n"
                sell_message += (
                    f"   Target Downside: <b>{result['target_upside']}%</b>\n"
                )
                sell_message += f"   Price Change: {result['price_change']}\n"
                sell_message += f"   Consensus: {result['consensus']}\n"
                sell_message += f"   P/E Ratio: {result['pe_ratio']}x\n\n"

            sell_message += f"Total SELL signals: {len(sell_results)} symbols found"
            telegram_message.append(sell_message)

            # Also print sell results to console
            print("\n" + "=" * 80)
            print(" SELL RESULTS:")
            print("=" * 80)
            for result in sell_results:
                print(
                    f"{result['symbol']}: {result['rating']} ({result['target_upside']}% target_downside) ({result['current_upside']}% current_downside)"
                )
            print("=" * 80)
        else:
            print("\n\n*** No SELL symbols matched the criteria. ***")
            sell_message = "<b>Investing Pro Strong SELL Alerts</b>\n\nNo symbols found with 'Strong sell' rating."
            telegram_message.append(sell_message)


asyncio.run(main())
