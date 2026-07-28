"""数据分析 API 路由"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/dashboard")
async def dashboard():
    """获取数据看板"""
    return {
        "overview": {
            "total_sessions": 12580,
            "today_sessions": 328,
            "ai_resolution_rate": 85.6,
            "avg_response_time": 1.2,
            "transfer_rate": 8.3,
        },
        "intent_distribution": [
            {"name": "订单查询", "value": 35},
            {"name": "商品咨询", "value": 28},
            {"name": "退款退货", "value": 15},
            {"name": "支付问题", "value": 8},
            {"name": "配送查询", "value": 5},
            {"name": "促销活动", "value": 4},
            {"name": "其他", "value": 5},
        ],
        "sentiment_distribution": [
            {"name": "正面", "value": 45},
            {"name": "中性", "value": 38},
            {"name": "负面", "value": 17},
        ],
        "satisfaction_trend": [
            {"date": "2026-01", "score": 3.2},
            {"date": "2026-02", "score": 3.3},
            {"date": "2026-03", "score": 3.5},
            {"date": "2026-04", "score": 3.6},
            {"date": "2026-05", "score": 3.7},
            {"date": "2026-06", "score": 3.8},
        ],
        "hourly_traffic": [
            {"hour": "00:00", "count": 45}, {"hour": "02:00", "count": 25},
            {"hour": "04:00", "count": 15}, {"hour": "06:00", "count": 35},
            {"hour": "08:00", "count": 120}, {"hour": "10:00", "count": 280},
            {"hour": "12:00", "count": 220}, {"hour": "14:00", "count": 310},
            {"hour": "16:00", "count": 260}, {"hour": "18:00", "count": 190},
            {"hour": "20:00", "count": 160}, {"hour": "22:00", "count": 100},
        ],
    }
