import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------------------------------------------
# SETUP: Page configuration
# -----------------------------------------------------------
st.set_page_config(page_title="Avalanche App", layout="wide")
st.title("Avalanche Streamlit App")

# -----------------------------------------------------------
# DATA LOADING: Caching prevents re-running SQL on every click
# -----------------------------------------------------------
@st.cache_data(ttl=3600)  # Cache data for 1 hour
def load_data():
    # st.connection automatically looks for secrets in .streamlit/secrets.toml
    # or the Streamlit Cloud "Secrets" dashboard.
    conn = st.connection("snowflake")
    
    query = """
    SELECT * FROM REVIEWS_WITH_SENTIMENT
    """
    
    # Use standard pandas execution for compatibility
    df = conn.query(query)
    
    # Convert dates immediately
    if 'REVIEW_DATE' in df.columns:
        df['REVIEW_DATE'] = pd.to_datetime(df['REVIEW_DATE'])
    if 'SHIPPING_DATE' in df.columns:
        df['SHIPPING_DATE'] = pd.to_datetime(df['SHIPPING_DATE'])
        
    return df

try:
    with st.spinner("Loading Snowflake data..."):
        df_reviews = load_data()
        # Create a string version for the chatbot context
        df_string = df_reviews.head(50).to_string(index=False) 
except Exception as e:
    st.error(f"❌ Connection Error: {e}")
    st.info("Did you set up your Secrets in the Streamlit Cloud dashboard?")
    st.stop()

# -----------------------------------------------------------
# VISUALIZATION 1: Average Sentiment
# -----------------------------------------------------------
st.subheader("Average Sentiment by Product")
if "PRODUCT" in df_reviews.columns and "SENTIMENT_SCORE" in df_reviews.columns:
    product_sentiment = df_reviews.groupby("PRODUCT")["SENTIMENT_SCORE"].mean().sort_values()

    fig, ax = plt.subplots(figsize=(8, 4))
    product_sentiment.plot(kind="barh", ax=ax, color='skyblue')
    ax.set_xlabel("Sentiment Score")
    ax.set_title("Average Sentiment by Product")
    st.pyplot(fig)
else:
    st.warning("Data missing required columns (PRODUCT, SENTIMENT_SCORE)")

# -----------------------------------------------------------
# INTERACTION: Filter by Product
# -----------------------------------------------------------
st.subheader("Filter by Product")
product = st.selectbox("Choose a product", ["All Products"] + list(df_reviews["PRODUCT"].unique()))

if product != "All Products":
    filtered_data = df_reviews[df_reviews["PRODUCT"] == product]
else:
    filtered_data = df_reviews

st.write(f"**Showing {len(filtered_data)} reviews**")
st.dataframe(filtered_data, use_container_width=True)

# -----------------------------------------------------------
# VISUALIZATION 2: Distribution
# -----------------------------------------------------------
st.subheader(f"Sentiment Distribution for {product}")
fig, ax = plt.subplots(figsize=(8, 4))
filtered_data['SENTIMENT_SCORE'].hist(ax=ax, bins=20, color='orange', edgecolor='white')
ax.set_title("Distribution of Sentiment Scores")
ax.set_xlabel("Sentiment Score")
ax.set_ylabel("Frequency")
st.pyplot(fig)

# -----------------------------------------------------------
# CHATBOT: Cortex
# -----------------------------------------------------------
st.divider()
st.subheader("🤖 Ask Questions About Your Data")
user_question = st.text_input("Enter your question here:")

if user_question:
    # Escape single quotes to prevent SQL errors
    safe_question = user_question.replace("'", "''")
    safe_context = df_string.replace("'", "''")
    
    prompt = f"Answer this question using the dataset: {safe_question} <context>{safe_context}</context>"
    
    # We use a fresh session call for Cortex
    # Note: Cortex COMPLETE syntax
    cortex_query = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('claude-3-5-sonnet', '{prompt}')"
    
    try:
        conn = st.connection("snowflake")
        # .collect() is a Snowpark method; .query() returns pandas.
        # We use .query() here for simplicity in Community Cloud
        result_df = conn.query(cortex_query) 
        response = result_df.iloc[0,0]
        st.success(response)
    except Exception as e:
        st.error(f"Error calling Cortex: {e}")
