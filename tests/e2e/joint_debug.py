"""
联合调试测试：Game 服务核心流程测试

测试场景：
1. 两个玩家通过 WebSocket 连接 Game 服务
2. 创建/加入房间
3. 游戏开始
4. 服务统计
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from starlette.testclient import TestClient
from internal.game.websocket_server import create_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("joint_debug")


def test_two_player_flow():
    """Test two-player game flow."""
    logger.info("\n" + "=" * 60)
    logger.info("联合调试测试 - 双人游戏流程")
    logger.info("=" * 60)

    # Create server
    room_id = f"test_{datetime.now().timestamp()}"
    server = create_server(host="127.0.0.1", port=8091)
    app = server.app

    results = {
        "connect_p1": False,
        "connect_p2": False,
        "p1_join": False,
        "p2_join": False,
        "p1_side": None,
        "p2_side": None,
        "game_started": False,
    }

    with TestClient(app) as client:
        # Player 1 connects
        logger.info("\n--- 玩家1 连接 ---")
        try:
            with client.websocket_connect(f"/game/{room_id}?user_id=1&username=player1") as ws1:
                results["connect_p1"] = True
                msg = ws1.receive_json()
                logger.info(f"玩家1 收到: {msg}")
                results["p1_join"] = msg.get("type") == "waiting"
                results["p1_side"] = msg.get("data", {}).get("side")

                # Player 2 connects - this triggers game start
                logger.info("\n--- 玩家2 连接 ---")
                with client.websocket_connect(f"/game/{room_id}?user_id=2&username=player2") as ws2:
                    results["connect_p2"] = True
                    msg = ws2.receive_json()
                    logger.info(f"玩家2 收到: {msg}")

                    if msg.get("type") == "game_start":
                        results["game_started"] = True
                        results["p2_side"] = msg.get("data", {}).get("your_side")
                        results["p2_join"] = True

                        # Player 1 should also receive game_start
                        msg1 = ws1.receive_json()
                        logger.info(f"玩家1 收到: {msg1}")
                        if msg1.get("type") == "game_start":
                            logger.info("✓ 双方都收到 game_start")

        except Exception as e:
            logger.error(f"测试异常: {e}", exc_info=True)

    # Print results
    logger.info("\n" + "=" * 60)
    logger.info("测试结果")
    logger.info("=" * 60)

    passed = 0
    failed = 0

    for key, value in results.items():
        status = "✓" if value else "✗"
        if value:
            passed += 1
        else:
            failed += 1
        logger.info(f"  {status} {key}: {value}")

    logger.info(f"\n通过: {passed}, 失败: {failed}")
    logger.info("=" * 60)

    return failed == 0


def test_server_endpoints():
    """Test server HTTP endpoints."""
    logger.info("\n" + "=" * 60)
    logger.info("测试服务 HTTP 端点")
    logger.info("=" * 60)

    server = create_server(host="127.0.0.1", port=8092)
    app = server.app

    with TestClient(app) as client:
        # Health check
        resp = client.get("/health")
        logger.info(f"Health: {resp.json()}")
        health_ok = resp.json().get("status") == "ok"

        # Stats check
        resp = client.get("/stats")
        logger.info(f"Stats: {resp.json()}")
        stats_ok = "active_connections" in resp.json()

    return health_ok and stats_ok


if __name__ == "__main__":
    logger.info("开始联合调试测试...")
    logger.info("测试 Game 服务核心功能")
    logger.info("")

    all_passed = True

    # Test 1: Server endpoints
    if not test_server_endpoints():
        all_passed = False

    # Test 2: Two player flow
    if not test_two_player_flow():
        all_passed = False

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("测试汇总")
    logger.info("=" * 60)

    if all_passed:
        logger.info("✓ 所有测试通过！")
        logger.info("")
        logger.info("已验证：")
        logger.info("  1. Game 服务 HTTP 端点 (/health, /stats)")
        logger.info("  2. WebSocket 连接建立")
        logger.info("  3. 房间创建与玩家加入")
        logger.info("  4. 双人游戏开始流程")
        sys.exit(0)
    else:
        logger.info("✗ 部分测试失败")
        sys.exit(1)
