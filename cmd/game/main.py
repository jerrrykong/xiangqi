"""Game service entry point."""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from internal.game.websocket_server import create_server


def setup_logging(level: str = "INFO") -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Xiangqi Game Service")
    parser.add_argument(
        "--host",
        default=os.getenv("GAME_HOST", "0.0.0.0"),
        help="Host to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("GAME_PORT", "8081")),
        help="Port to bind to",
    )
    parser.add_argument(
        "--web-callback-url",
        default=os.getenv("WEB_CALLBACK_URL", "http://localhost:8080/internal/game/result"),
        help="Web service callback URL",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.log_level)

    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("Xiangqi Game Service")
    logger.info("=" * 50)
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Web Callback URL: {args.web_callback_url}")
    logger.info("=" * 50)

    server = create_server(
        host=args.host,
        port=args.port,
        game_callback_url=args.web_callback_url,
    )

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
