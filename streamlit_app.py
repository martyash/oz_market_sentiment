import praw
import re
import math
import os
from google import genai
import json
import streamlit as st 

# Initialize Reddit API
reddit = praw.Reddit(
    client_id=st.secrets["client_id"],
    client_secret=st.secrets["client_secret"],
    user_agent= st.secrets["user_agent"]
)

subreddit = reddit.subreddit("ausfinance")

asx_keywords = ['asx', 'stocks', 'shares', 'market', 'etf', 'investing in shares', 'dividend', 'portfolio', 
                'bullish', 'vanguard', 'profit', 'buffet', 'mining', 'lambos','crypto','bitcoin','gold']

posts_data = []

# Scrape top posts/comments from the last week
for submission in subreddit.top(time_filter='week', limit=20):
    submission.comments.replace_more(limit=0)
    for comment in submission.comments.list():
        if comment.score > 40:
            posts_data.append({
                'post_title': submission.title,
                'post_score': submission.score,
                'comment_body': comment.body,
                'comment_score': comment.score
            })

def is_stock_related(post_title, comment_body):
    combined_text = f"{post_title} {comment_body}"
    return any(re.search(rf'\b{k}\b', combined_text, re.I) for k in asx_keywords)

# Filter comments related to stocks
stock_comments = [c for c in posts_data if is_stock_related(c['post_title'], c['comment_body'])]

if not stock_comments:
    print("No relevant stock-related comments found today.")
else:
    # Initialize Google Gemini API
    client = genai.Client(api_key= st.secrets["gemini"])



    # Prepare batch request for all comments
    comments_text = [c['comment_body'] for c in stock_comments]


    # Correct structure for Gemini API
    prompt = (
    "Classify the sentiment of the following comments from a finance forum into one of these categories:\n\n"
    "1. **Bullish** – Indicates confidence in rising prices, optimism about stocks, economy, or investments.\n"
    "2. **Bearish** – Indicates pessimism, expecting falling prices, recession concerns, or negative outlook.\n"
    "3. **Neutral** – Provides factual statements, balanced arguments, or does not indicate clear sentiment.\n"
    "4. **Speculative** – Discusses potential risks, rumors, or uncertain market predictions.\n"
    "5. **Fear/Uncertainty/Doubt (FUD)** – Spreading fear or uncertainty about the market, economy, or specific assets.\n"
    "6. **Joke/Satire** – Sarcastic, humorous, or ironic comment about finance or investing.\n"
    "7. **Offtopic** – Not related to finance, investments, or market discussion.\n\n"
    "Return output in JSON format as a list of dictionaries with 'comment' and 'sentiment_label'.\n\n"
    )   


      # Construct the API request properly
    contents = [{"parts": [{"text": prompt + "\n".join([f"{idx+1}. {comment}" for idx, comment in enumerate(comments_text)])}]}]


    
    # Make the API request
    response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=contents
    )

    raw_response = response.candidates[0].content.parts[0].text  # Extract text
    # Remove triple backticks and the "json" keyword from the start
    cleaned_text = re.sub(r"^```json\n|\n```$", "", raw_response.strip())
    sentiment_results = json.loads(cleaned_text)

    # Attach sentiment labels to stock_comments safely
    for i in range(len(stock_comments)):
        stock_comments[i]['sentiment_label'] = sentiment_results[i].get('sentiment_label', "Unknown")  # Prevent KeyError

    # Sort comments by log(upvotes) for ranking
    stock_comments.sort(key=lambda c: math.log(c['comment_score'] + 1), reverse=True)

    # STREAMLIT SECTION 

    # Define sentiment icons
    sentiment_icons = {
    "Bullish": "🚀📈💰",  # Rocket, chart up, money bag
    "Bearish": "📉😬🔻",  # Chart down, worried face, red arrow down
    "Neutral": "😐📊🤷",  # Neutral face, bar chart, shrug
    "Speculative": "🤔🔮📉",  # Thinking face, crystal ball, chart down
    "Fear/Uncertainty/Doubt (FUD)": "😨📉🔥",  # Scared face, chart down, fire (panic)
    "Joke/Satire": "😂🤣🤑",  # Laughing faces, money tongue
    "Offtopic": "🚫🙅🗑️",  # No entry, stop hand, trash bin
    "Unknown": "❓🤷‍♂️🤷‍♀️",  # Question mark, shrugging
    }


    st.markdown("""
    <style>
        h1 { font-size: 36px !important; }
        h3 { font-size: 24px !important; }
        p { font-size: 18px !important; }
    </style>
""", unsafe_allow_html=True)

    # Display results
    st.subheader("📢 Top 10 market sentiments from r/ausfinance This week")
    for idx, comment in enumerate(stock_comments[:10], 1):
        st.markdown(f"""
        **{idx}. {comment['post_title']}**
        - 🗨️ *"{comment['comment_body']}"*
        -  **upvotes 🔼** {comment['comment_score']}
        -  **Sentiment:** {sentiment_icons.get(comment['sentiment_label'], '❓')} {comment.get('sentiment_label', 'Unknown')}
        ---
        """)

    
   