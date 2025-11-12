import json
from openai import OpenAI
class AIService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def generate_summary(self, content: str) -> dict:
        """Generate news summary with impact and reason"""
        messages = [
            {
                "role": "system",
                "content": "你是一個新聞摘要生成機器人,請統整新聞中提及的影響及主要原因 (影響、原因各50個字,請以json格式回答 {'影響': '...', '原因': '...'})",
            },
            {"role": "user", "content": content},
        ]
        
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        result = completion.choices[0].message.content
        return json.loads(result)
    
    def extract_keywords(self, prompt: str) -> str:
        """Extract search keywords from user prompt"""
        messages = [
            {
                "role": "system",
                "content": "你是一個關鍵字提取機器人,用戶將會輸入一段文字,表示其希望看見的新聞內容,請提取出用戶希望看見的關鍵字,請截取最重要的關鍵字即可,避免出現「新聞」、「資訊」等混淆搜尋引擎的字詞。(僅須回答關鍵字,若有多個關鍵字,請以空格分隔)",
            },
            {"role": "user", "content": prompt},
        ]
        
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        return completion.choices[0].message.content
    
    def evaluate_relevance(self, title: str) -> str:
        """Evaluate news relevance to price changes"""
        messages = [
            {
                "role": "system",
                "content": "你是一個關聯度評估機器人,請評估新聞標題是否與「民生用品的價格變化」相關,並給予'high'、'medium'、'low'評價。(僅需回答'high'、'medium'、'low'三個詞之一)",
            },
            {"role": "user", "content": title},
        ]
        
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        return completion.choices[0].message.content