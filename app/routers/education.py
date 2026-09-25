from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/education", tags=["education"])

TOPICS = [
    {
        "slug": "candlestick-basics",
        "title": "Reading Candlestick Charts",
        "category": "Basics",
        "summary": "What a candlestick shows and how to read bullish vs bearish candles.",
        "content": (
            "Each candlestick shows four prices for a time period: open, high, low, "
            "and close. A filled/red candle usually means the close was lower than "
            "the open (bearish); a hollow/green candle means the close was higher "
            "(bullish). The thin lines above and below the body are 'wicks' or "
            "'shadows' showing the highest and lowest prices reached.\n\n"
            "Longer bodies signal stronger buying or selling pressure. Long wicks "
            "show rejection of a price level - a long lower wick can mean buyers "
            "stepped in after a drop, while a long upper wick can mean sellers "
            "capped a rally."
        ),
    },
    {
        "slug": "support-resistance",
        "title": "Support and Resistance",
        "category": "Basics",
        "summary": "Understanding the price zones where trends often pause or reverse.",
        "content": (
            "Support is a price zone where falling prices have repeatedly found "
            "buyers, causing a bounce. Resistance is the opposite: a zone where "
            "rising prices have repeatedly met sellers.\n\n"
            "These are zones, not exact lines - price often pokes through slightly "
            "before reversing. When resistance breaks, it often becomes new "
            "support ('role reversal'), and vice versa."
        ),
    },
    {
        "slug": "trend-lines",
        "title": "Trend Lines & Trend Structure",
        "category": "Basics",
        "summary": "How to draw trend lines and identify uptrends, downtrends, and ranges.",
        "content": (
            "An uptrend is a series of higher highs and higher lows; a downtrend "
            "is a series of lower highs and lower lows. A range-bound market moves "
            "sideways between support and resistance.\n\n"
            "A trend line connects at least two swing lows (in an uptrend) or "
            "swing highs (in a downtrend). The more times price respects a trend "
            "line, the more significant it's considered."
        ),
    },
    {
        "slug": "chart-patterns",
        "title": "Common Chart Patterns",
        "category": "Patterns",
        "summary": "Head & shoulders, double tops/bottoms, triangles, flags, and what they suggest.",
        "content": (
            "Head & Shoulders: three peaks, the middle one highest, often signals "
            "a top reversal. Inverse head & shoulders signals a bottom reversal.\n\n"
            "Double Top / Double Bottom: price tests a level twice and fails to "
            "break through, suggesting a reversal.\n\n"
            "Triangles: price consolidates into a narrowing range before typically "
            "breaking out in the direction of the prevailing trend.\n\n"
            "Flags & Pennants: brief consolidations after a strong move, usually "
            "continuation patterns."
        ),
    },
    {
        "slug": "moving-averages",
        "title": "Moving Averages (SMA & EMA)",
        "category": "Indicators",
        "summary": "How moving averages smooth price data and signal trend direction.",
        "content": (
            "A Simple Moving Average (SMA) averages closing prices over N periods. "
            "An Exponential Moving Average (EMA) weights recent prices more "
            "heavily.\n\n"
            "Common periods: 20, 50, 100, 200. Price above a rising moving average "
            "generally suggests an uptrend. A 'golden cross' (short-term MA "
            "crossing above a long-term MA) is viewed as bullish."
        ),
    },
    {
        "slug": "rsi",
        "title": "RSI - Relative Strength Index",
        "category": "Indicators",
        "summary": "A momentum oscillator used to spot overbought/oversold conditions.",
        "content": (
            "RSI ranges from 0 to 100. Readings above 70 are traditionally "
            "considered 'overbought'; readings below 30 are 'oversold'.\n\n"
            "RSI can also show 'divergence': if price makes a new high but RSI "
            "makes a lower high, momentum may be weakening."
        ),
    },
    {
        "slug": "macd",
        "title": "MACD - Moving Average Convergence Divergence",
        "category": "Indicators",
        "summary": "A trend-following momentum indicator built from two EMAs.",
        "content": (
            "MACD is calculated from the difference between a 12-period EMA and a "
            "26-period EMA, plotted alongside a 9-period EMA signal line.\n\n"
            "When the MACD line crosses above the signal line, it's often read as "
            "bullish momentum building; crossing below is often read as bearish."
        ),
    },
    {
        "slug": "volume",
        "title": "Volume Analysis",
        "category": "Indicators",
        "summary": "Why volume confirms (or questions) a price move.",
        "content": (
            "A price move on high volume is generally considered more meaningful "
            "than the same move on low volume.\n\n"
            "Breakouts on strong volume are considered more reliable; breakouts "
            "on weak volume more often fail ('false breakout')."
        ),
    },
    {
        "slug": "risk-management",
        "title": "Basic Risk Management",
        "category": "Trading Discipline",
        "summary": "Position sizing, stop-losses, and why risk management matters more than any indicator.",
        "content": (
            "No indicator or pattern works every time. Risk management is what "
            "keeps one bad trade from causing serious damage: risking only a "
            "small percentage of a portfolio per trade, setting a stop-loss "
            "before entering, and defining an exit plan in advance."
        ),
    },
]


@router.get("", response_model=None)
def list_topics():
    return [{k: v for k, v in t.items() if k != "content"} for t in TOPICS]


@router.get("/{slug}", response_model=None)
def get_topic(slug: str):
    for t in TOPICS:
        if t["slug"] == slug:
            return t
    raise HTTPException(status_code=404, detail="Topic not found")
