import os
import random
import time
import requests
import tweepy
import google.generativeai as genai
from datetime import datetime, timedelta

# ── 環境変数から設定を読み込む ──────────────────────────────────
NEWS_API_KEY          = os.environ["NEWS_API_KEY"]
GEMINI_API_KEY        = os.environ["GEMINI_API_KEY"]
X_API_KEY             = os.environ["X_API_KEY"]
X_API_SECRET          = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN        = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_TOKEN_SECRET = os.environ["X_ACCESS_TOKEN_SECRET"]

# ローカル実行時は .env ファイルから読み込む (python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
    NEWS_API_KEY          = os.environ.get("NEWS_API_KEY", NEWS_API_KEY)
    GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
    X_API_KEY             = os.environ.get("X_API_KEY", X_API_KEY)
    X_API_SECRET          = os.environ.get("X_API_SECRET", X_API_SECRET)
    X_ACCESS_TOKEN        = os.environ.get("X_ACCESS_TOKEN", X_ACCESS_TOKEN)
    X_ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", X_ACCESS_TOKEN_SECRET)
except ImportError:
    pass


# ── ニュース取得 ──────────────────────────────────────────────
def fetch_ai_news() -> list[dict]:
    """NewsAPI から最新の AI ニュースを取得する（日本語→英語フォールバック）"""
    url = "https://newsapi.org/v2/everything"

    # 検索クエリをランダムに選んで多様性を出す
    queries_ja = [
        "人工知能 OR 生成AI OR ChatGPT OR Claude OR Gemini",
        "LLM OR 大規模言語モデル OR AI エージェント",
        "OpenAI OR Anthropic OR Google AI OR Microsoft AI",
    ]
    queries_en = [
        "artificial intelligence OR ChatGPT OR LLM",
        "OpenAI OR Anthropic OR Claude OR Gemini",
        "AI agent OR generative AI OR foundation model",
    ]

    # まず日本語記事を試みる
    params = {
        "q": random.choice(queries_ja),
        "language": "ja",
        "sortBy": "publishedAt",
        "pageSize": 15,
        "from": (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d"),
        "apiKey": NEWS_API_KEY,
    }
    res = requests.get(url, params=params, timeout=10)
    articles = res.json().get("articles", [])

    # 日本語記事が少なければ英語記事も取得
    if len(articles) < 5:
        params_en = params.copy()
        params_en["q"] = random.choice(queries_en)
        params_en["language"] = "en"
        res_en = requests.get(url, params=params_en, timeout=10)
        articles += res_en.json().get("articles", [])

    # タイトルや説明が空の記事を除外
    articles = [
        a for a in articles
        if a.get("title") and a.get("description")
        and "[Removed]" not in a.get("title", "")
    ]
    return articles


# ── ツイート文生成 ────────────────────────────────────────────
def generate_tweet(article: dict) -> tuple[str, str]:
    """Gemini API を使って人間らしいツイート文を生成する"""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    title       = article.get("title", "")
    description = article.get("description", "")
    source      = article.get("source", {}).get("name", "")
    article_url = article.get("url", "")

    # 人間らしさを出すためにスタイルをランダムに変える
    styles = [
        "驚き・ワクワク感を込めた反応（「えっ、これすごくない？」「マジか！」系）",
        "冷静な分析・批評（「〜という点が気になる」「〜はどうなんだろう」系）",
        "共感を求める語りかけ（「みんなはどう思う？」「〜だと思うんだよね」系）",
        "身近な視点からの考察（「これ仕事に使えそう」「日常がどう変わるか考えてみた」系）",
        "少し皮肉・懐疑的（「また〜か」「これ本当に大丈夫なのかな」系）",
    ]
    style = random.choice(styles)

    # 語尾・口調バリエーション（毎回違う雰囲気にする）
    tone_hints = [
        "語尾は「〜だな」「〜だね」など柔らかい男性口調",
        "語尾は「〜ですよね」「〜だと思います」など丁寧だが堅くない口調",
        "語尾は「〜じゃん」「〜だわ」などカジュアルな口調",
        "「！」を1〜2個使って感情を表現しつつ、話し言葉で書く",
        "体言止めや省略を使い、テンポよく書く",
    ]
    tone = random.choice(tone_hints)

    # ハッシュタグを付けるかどうかをランダムに決める（付けすぎると bot っぽい）
    hashtag_instruction = random.choice([
        "ハッシュタグは付けない",
        "関連する日本語ハッシュタグを1つだけ末尾に付ける（例: #生成AI）",
        "ハッシュタグは付けない",  # 付けない確率を高めに設定
        "#AI か #人工知能 を1つだけ末尾に付ける",
    ])

    prompt = f"""以下のAIニュースについて、Xに投稿するツイート文を1つ作成してください。

【記事情報】
タイトル: {title}
概要: {description}
出典: {source}

【作成条件】
- スタイル: {style}
- 口調: {tone}
- {hashtag_instruction}
- URLは含めない（自動で追加されます）
- 日本語で書く
- 120文字以内（URLが別途追加されるため短めに）
- 絵文字は使わない
- 「〜というニュースが〜」のような紹介文にしない。自分の意見・感想・考察を中心に書く
- 実際に人間がスマホで打ったような自然な文体にする

ツイート本文のみを出力してください（説明・前置き・引用符は不要）。"""

    response = model.generate_content(prompt)
    tweet_text = response.text.strip()
    return tweet_text, article_url


# ── X への投稿 ────────────────────────────────────────────────
def post_tweet(tweet_text: str, url: str = "") -> dict:
    """tweepy v2 でツイートを投稿する"""
    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET,
    )

    # URL が短くて余裕があれば追加（X の URL は 23 文字換算）
    url_length = 24  # 改行 + 23文字
    if url and len(tweet_text) + url_length <= 280:
        full_text = f"{tweet_text}\n{url}"
    else:
        full_text = tweet_text

    print(f"[POST] {full_text}")
    response = client.create_tweet(text=full_text)
    return response.data


# ── メイン処理 ────────────────────────────────────────────────
def main():
    # 人間らしさを演出するためにランダムに遅延（0〜20分）
    # GitHub Actions で毎日 9:00 JST 実行 → 実際には 9:00〜9:20 の間にランダム投稿
    delay_sec = random.randint(0, 20 * 60)
    print(f"[WAIT] {delay_sec // 60}分{delay_sec % 60}秒待機してから投稿します...")
    time.sleep(delay_sec)

    # ニュースを取得
    print("[FETCH] AI ニュースを取得中...")
    articles = fetch_ai_news()
    if not articles:
        print("[ERROR] ニュース記事が見つかりませんでした")
        return

    # 上位 5 件からランダムに選択（最新記事に偏らせる）
    candidates = articles[:5]
    article = random.choice(candidates)
    print(f"[SELECT] 記事: {article.get('title')}")

    # ツイート文を生成
    print("[GENERATE] ツイート文を生成中...")
    tweet_text, article_url = generate_tweet(article)
    print(f"[TWEET] {tweet_text}")
    print(f"[URL]   {article_url}")

    # 投稿
    result = post_tweet(tweet_text, article_url)
    print(f"[SUCCESS] ツイート投稿完了: tweet_id={result.get('id')}")


if __name__ == "__main__":
    main()
