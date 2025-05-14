#!/usr/bin/env python3
"""
Website Status Check Plugin for Nagios.

This plugin checks the status of a website by sending an HTTP request and
validating the response. It can check for specific patterns in the response
content and measure response time.

Usage:
    check_website_status.py --url URL [--pattern PATTERN] [--warning SECONDS]
                           [--critical SECONDS] [--timeout SECONDS]
                           [--no-verify-ssl] [--json] [--verbose]

Returns:
    0 (OK): Website is responding correctly within time thresholds
    1 (WARNING): Website is responding but took longer than warning threshold
    2 (CRITICAL): Website is not responding or does not match expected pattern
    3 (UNKNOWN): An unexpected error occurred during the check
"""

import argparse
import logging
import re
import sys
from typing import Optional

import httpx
from rich.console import Console
from rich.logging import RichHandler

from nagios_plugins.base import Status, CheckResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("check_website_status")


class WebsiteStatusChecker:
    """Website status checker."""

    def __init__(
        self,
        url: str,
        pattern: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True,
        warning_threshold: Optional[float] = None,
        critical_threshold: Optional[float] = None,
    ):
        """Initialize the website status checker.

        Args:
            url: URL to check
            pattern: Regex pattern to search for in the response
            timeout: HTTP request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            warning_threshold: Warning threshold in seconds
            critical_threshold: Critical threshold in seconds
        """
        self.url = url
        self.pattern = re.compile(pattern) if pattern else None
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.console = Console()

    async def check_website(self) -> CheckResult:
        """Check the website status.

        Returns:
            CheckResult with the check result
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, verify=self.verify_ssl, follow_redirects=True
            ) as client:
                # Make the request and capture timing information
                response = await client.get(self.url)
                duration = response.elapsed.total_seconds()

                # Check HTTP status code
                if response.status_code >= 400:
                    return CheckResult(
                        Status.CRITICAL,
                        f"HTTP {response.status_code} error",
                        metrics={"status_code": response.status_code, "duration": duration},
                        details=f"URL: {self.url}\nResponse: {response.text[:500]}...",
                    )

                # Check for pattern if specified
                if self.pattern and not self.pattern.search(response.text):
                    return CheckResult(
                        Status.CRITICAL,
                        f"Pattern not found in response",
                        metrics={
                            "status_code": response.status_code,
                            "duration": duration,
                            "pattern_found": 0,
                        },
                        details=(
                            f"URL: {self.url}\nPattern: {self.pattern.pattern}\n"
                            f"Response snippet: {response.text[:500]}..."
                        ),
                    )

                # Check response time thresholds
                status = Status.OK
                message = "Website OK - response time " + str(round(duration, 2)) + "s"

                if self.critical_threshold and duration > self.critical_threshold:
                    status = Status.CRITICAL
                    message = (
                        f"Response time {duration:.2f}s exceeds critical"
                        f" threshold {self.critical_threshold}s"
                    )
                elif self.warning_threshold and duration > self.warning_threshold:
                    status = Status.WARNING
                    message = (
                        f"Response time {duration:.2f}s exceeds warning"
                        f" threshold {self.warning_threshold}s"
                    )

                # Create metrics
                metrics = {
                    "status_code": response.status_code,
                    "duration": duration,
                }

                if self.pattern:
                    metrics["pattern_found"] = 1

                # Extract interesting values from response for metrics
                # Look for key=value or "key": value patterns in the response
                for pattern in [r"(\w+)=(\w+)", r'"(\w+)":\s*"?([^",]+)"?']:
                    for match in re.finditer(pattern, response.text):
                        key, value = match.groups()
                        # Only include numeric values or boolean-like values
                        if value.isdigit() or value.lower() in ("true", "false"):
                            try:
                                if value.isdigit():
                                    metrics[key] = int(value)
                                else:
                                    metrics[key] = value.lower() == "true"
                            except (ValueError, TypeError):
                                pass

                return CheckResult(
                    status,
                    message,
                    metrics=metrics,
                )

        except httpx.TimeoutException:
            return CheckResult(
                Status.CRITICAL,
                f"Request timed out after {self.timeout}s",
                metrics={"duration": self.timeout},
                details=f"URL: {self.url}",
            )
        except httpx.HTTPError as e:
            return CheckResult(
                Status.CRITICAL,
                f"HTTP error: {str(e)}",
                metrics={"duration": 0},
                details=f"URL: {self.url}\nError: {str(e)}",
            )
        except Exception as e:
            logger.exception("Unexpected error")
            return CheckResult(
                Status.UNKNOWN,
                f"Unexpected error: {str(e)}",
                metrics={"duration": 0},
                details=f"URL: {self.url}\nError: {str(e)}",
            )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Check website status",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL to check",
    )
    parser.add_argument(
        "--pattern",
        help="Regex pattern to search for in the response",
    )
    parser.add_argument(
        "--warning",
        type=float,
        help="Warning threshold for response time in seconds",
    )
    parser.add_argument(
        "--critical",
        type=float,
        help="Critical threshold for response time in seconds",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP request timeout in seconds",
    )
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        help="Disable SSL certificate verification",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    parser.add_argument(
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (can be used multiple times)",
    )

    return parser.parse_args()


async def main_async() -> int:
    """Main async function.

    Returns:
        Exit code
    """
    args = parse_args()

    # Set logging level based on verbosity
    if args.verbose == 1:
        logger.setLevel(logging.INFO)
    elif args.verbose >= 2:
        logger.setLevel(logging.DEBUG)

    # Create checker and run check
    checker = WebsiteStatusChecker(
        url=args.url,
        pattern=args.pattern,
        timeout=args.timeout,
        verify_ssl=not args.no_verify_ssl,
        warning_threshold=args.warning,
        critical_threshold=args.critical,
    )

    result = await checker.check_website()

    # Output the result
    if args.json:
        print(result.to_json())
    else:
        print(result)

    return result.status.value


def main() -> int:
    """Main function.

    Returns:
        Exit code
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(main_async())


if __name__ == "__main__":
    sys.exit(main())
