#Script to generate stock candle chart, upload it to imagekit.io, and analyze it using OpenAI
#Current issues: write permissions prevent full script execution, stops at [INFO] Generating candlestick chart for {ticker}...
import os
import time
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from imagekitio import ImageKit
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables (ensure API keys are in .env)
load_dotenv()

# Initialize OpenAI client
client = OpenAI()

# Initialize ImageKit client
imagekit = ImageKit(
    private_key='your_imagekit_private_key',
    public_key='your_imagekit_public_key',
    url_endpoint='https://ik.imagekit.io/{your_imagekit_endpoint}'
)

def plot_candlestick_chart(ticker, data):
    """Generate and save a Plotly candlestick chart."""
    print(f"[INFO] Generating candlestick chart for {ticker}...")
    
    fig = go.Figure()

    # Add candlestick chart
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        increasing_line_color='green',
        decreasing_line_color='red',
        increasing_fillcolor='rgba(0, 255, 0, 0.5)',
        decreasing_fillcolor='rgba(255, 0, 0, 0.5)'
    ))

    # Set title and labels
    fig.update_layout(
        title=f"{ticker} Candlestick Chart",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False
    )

    # Save the chart locally
    image_path = f"{ticker}_candlestick_chart.png"

    import os
    
    save_directory = os.path.expanduser("~/Documents")  # Change to a known writable directory
    image_path = os.path.join(save_directory, f"{ticker}_candlestick_chart.png")
    
    try:
        fig.write_image(image_path, engine="kaleido")
        print(f"[SUCCESS] Chart saved at: {image_path}")
    except Exception as e:
        print(f"[ERROR] Failed to save chart: {e}")

   

    print(f"[SUCCESS] Chart saved: {image_path}")
    return image_path

def upload_image_to_imagekit(image_path):
    """Uploads an image to ImageKit.io and returns the HTTPS URL."""
    print(f"[INFO] Uploading {image_path} to ImageKit.io...")

    try:
        with open(image_path, "rb") as file:
            response = imagekit.upload(file=file, file_name=os.path.basename(image_path))

        # Extract URL
        image_url = getattr(response, "url", None)
        if not image_url:
            print(f"[ERROR] No URL returned from ImageKit.")
            return None
        
        print(f"[SUCCESS] Image uploaded: {image_url}")
        return image_url

    except Exception as e:
        print(f"[ERROR] Image upload failed: {e}")
        return None

def generate_ai_analysis(data_summary, image_url):
    """Generate detailed analysis using OpenAI API, including chart analysis."""
    if not image_url:
        return "[ERROR] No valid image URL provided."

    prompt = f"""
    Analyze the following stock data summary and the provided candlestick chart. 
    Provide insights on price action, volatility, trends, and market behavior.

    Data Summary:
    {data_summary}
    """

    print("[INFO] Sending request to OpenAI GPT-4o...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}
            ],
            max_tokens=500,
            timeout=30  # Timeout after 30 seconds
        )

        ai_analysis = response.choices[0].message.content.strip()
        print("[SUCCESS] OpenAI analysis received.")
        return ai_analysis

    except Exception as e:
        print(f"[ERROR] OpenAI request failed: {e}")
        return "Error generating analysis."

def wick_analysis(ticker, start_date, end_date):
    """Perform wick analysis, generate a chart, upload it, and get AI insights."""
    print(f"[INFO] Fetching stock data for {ticker} ({start_date} to {end_date})...")

    # Download historical data
    data = yf.download(ticker, start=start_date, end=end_date, interval="1d")
    if data.empty:
        print("[ERROR] No data found.")
        return "No data available for the given date range."

    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not all(col in data.columns for col in required_columns):
        print("[ERROR] Missing required columns in stock data.")
        return "The required columns are missing from the data."

    # Drop NaN rows and ensure numeric format
    data = data[required_columns].dropna().astype(float)
    data.index = pd.to_datetime(data.index)

    # Calculate wick sizes and body sizes
    high_price = data['High']
    low_price = data['Low']
    open_price = data['Open']
    close_price = data['Close']

    data['Upper_Wick'] = high_price - close_price.where(close_price > open_price, open_price)
    data['Lower_Wick'] = close_price.where(close_price < open_price, open_price) - low_price
    data['Body_Size'] = (close_price - open_price).abs()
    data['Total_Candle'] = high_price - low_price
    data['Wick_Score'] = data['Upper_Wick'] + data['Lower_Wick']

    # Summary statistics
    upper_wick_avg = data['Upper_Wick'].mean()
    lower_wick_avg = data['Lower_Wick'].mean()
    body_size_avg = data['Body_Size'].mean()
    total_candle_avg = data['Total_Candle'].mean()
    wick_score_avg = data['Wick_Score'].mean()

    # Prepare summary for AI analysis
    data_summary = f"""
    Average Upper Wick: {upper_wick_avg:.2f}
    Average Lower Wick: {lower_wick_avg:.2f}
    Average Body Size: {body_size_avg:.2f}
    Average Total Candle: {total_candle_avg:.2f}
    Average Wick Score: {wick_score_avg:.2f}
    """

    # Generate the candlestick chart
    image_path = plot_candlestick_chart(ticker, data)

    # Upload the image to ImageKit and retrieve the URL
    image_url = upload_image_to_imagekit(image_path)

    if not image_url:
        print("[ERROR] Image upload failed, skipping AI analysis.")
        return "Image upload failed."

    # Generate AI analysis with the chart and data summary
    ai_analysis = generate_ai_analysis(data_summary, image_url)

    # Generate a report
    report = f"""
    Wick Analysis Report for {ticker} ({start_date} to {end_date})
    --------------------------------------------------------------
    {data_summary}

    AI-Generated Insights:
    {ai_analysis}
    
    Chart URL: {image_url}
    """

    # Save detailed table to a CSV file
    output_filename = f"{ticker}_wick_analysis.csv"
    data[['Upper_Wick', 'Lower_Wick', 'Body_Size', 'Total_Candle', 'Wick_Score']].to_csv(output_filename)
    report += f"\nA detailed wick analysis table has been saved as '{output_filename}'."

    print("[SUCCESS] Wick analysis complete.")
    return report

# Example usage
ticker = input("Enter the stock ticker (e.g., INTU): ").strip().upper()
start_date = "2024-10-15" #input("Enter the start date (YYYY-MM-DD): ").strip()
end_date = "2025-02-06"#input("Enter the end date (YYYY-MM-DD): ").strip()

report = wick_analysis(ticker, start_date, end_date)
print(report)
