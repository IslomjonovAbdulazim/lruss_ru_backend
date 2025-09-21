# Translation API

## Overview

The Translation API provides high-quality Uzbek ↔ Russian translation using OpenAI GPT-3.5-turbo with intelligent caching to optimize performance and reduce costs.

## Base URL

```
https://your-api-domain.com/api/translation
```

## Authentication

```
Authorization: Bearer <access_token>
```

## Endpoint

### POST /translate

Translate text between Uzbek and Russian with automatic caching.

**Request:**
```bash
POST /api/translation/translate
Authorization: Bearer <your_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "text": "Salom, qalaysiz?",
  "target_language": "ru"
}
```

**Response:**
```json
{
  "input_text": "Salom, qalaysiz?",
  "target_language": "ru",
  "output_text": "Привет, как дела?",
  "from_cache": false
}
```

## Request Schema

### TranslationRequest
- `text` (string, required) - Text to translate (cannot be empty)
- `target_language` (string, required) - Target language code ("uz" or "ru")

## Response Schema

### TranslationResponse
- `input_text` (string) - Original text that was translated
- `target_language` (string) - Target language code
- `output_text` (string) - Translated text
- `from_cache` (boolean) - Whether result came from cache (true) or fresh translation (false)

## Supported Languages

| Code | Language | Direction |
|------|----------|-----------|
| `uz` | Uzbek | From Russian to Uzbek |
| `ru` | Russian | From Uzbek to Russian |

## Translation Examples

### Uzbek to Russian
```json
{
  "text": "Men rus tilini o'rganaman",
  "target_language": "ru"
}
```
**Response:**
```json
{
  "input_text": "Men rus tilini o'rganaman",
  "target_language": "ru",
  "output_text": "Я изучаю русский язык",
  "from_cache": false
}
```

### Russian to Uzbek
```json
{
  "text": "Добро пожаловать в наше приложение",
  "target_language": "uz"
}
```
**Response:**
```json
{
  "input_text": "Добро пожаловать в наше приложение",
  "target_language": "uz",
  "output_text": "Bizning ilovamizga xush kelibsiz",
  "from_cache": false
}
```

### Common Phrases
```json
{
  "text": "Rahmat sizga",
  "target_language": "ru"
}
```
**Response:**
```json
{
  "input_text": "Rahmat sizga",
  "target_language": "ru",
  "output_text": "Спасибо вам",
  "from_cache": true
}
```

## Caching System

### How It Works
1. **First Request**: Text is translated using OpenAI API and saved to database
2. **Subsequent Requests**: Same text returns cached result instantly
3. **Cache Key**: Combination of input text + target language
4. **Performance**: Cached results return in milliseconds vs seconds for API calls

### Cache Benefits
- **Fast Response**: Instant results for previously translated text
- **Cost Optimization**: Reduces OpenAI API usage and costs
- **Consistent Results**: Same input always returns same translation
- **Offline Capability**: Works even if OpenAI API is temporarily unavailable

## Error Responses

### 400 Bad Request - Invalid Language
```json
{
  "detail": "Invalid target language. Only uz, ru are supported."
}
```

### 400 Bad Request - Empty Text
```json
{
  "detail": "Input text cannot be empty"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 500 Internal Server Error - API Issue
```json
{
  "detail": "Translation failed: OpenAI API error"
}
```

### 500 Internal Server Error - Service Error
```json
{
  "detail": "Translation service error: Database connection failed"
}
```

## Usage Examples

### JavaScript/React Integration
```javascript
const translateText = async (text, targetLanguage) => {
  try {
    const response = await fetch('/api/translation/translate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        text: text,
        target_language: targetLanguage
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      console.log('Translation:', data.output_text);
      console.log('From cache:', data.from_cache);
      return data.output_text;
    } else {
      console.error('Translation error:', data.detail);
      return null;
    }
  } catch (error) {
    console.error('Network error:', error);
    return null;
  }
};

// Usage examples
translateText("Salom", "ru").then(result => {
  console.log(result); // "Привет"
});

translateText("Спасибо", "uz").then(result => {
  console.log(result); // "Rahmat"
});
```

### Flutter/Dart Integration
```dart
class TranslationService {
  static const String baseUrl = 'https://your-api-domain.com';
  
  Future<TranslationResponse?> translateText(String text, String targetLanguage) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/translation/translate'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: json.encode({
          'text': text,
          'target_language': targetLanguage,
        }),
      );
      
      if (response.statusCode == 200) {
        return TranslationResponse.fromJson(json.decode(response.body));
      } else {
        print('Translation error: ${response.body}');
        return null;
      }
    } catch (e) {
      print('Network error: $e');
      return null;
    }
  }
}

// Usage example
final translationService = TranslationService();
final result = await translationService.translateText("Salom", "ru");
if (result != null) {
  print('Translation: ${result.outputText}');
  print('From cache: ${result.fromCache}');
}
```

### Python Integration
```python
import requests
import json

def translate_text(text, target_language, token):
    url = "https://your-api-domain.com/api/translation/translate"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "target_language": target_language
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            return result["output_text"]
        else:
            print(f"Error: {response.json()['detail']}")
            return None
    except Exception as e:
        print(f"Network error: {e}")
        return None

# Usage examples
translation = translate_text("Salom dunyo", "ru", "your_jwt_token")
print(translation)  # "Привет, мир"
```

## UI Implementation Tips

### Real-time Translation
```javascript
const TranslationComponent = () => {
  const [inputText, setInputText] = useState('');
  const [translatedText, setTranslatedText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [language, setLanguage] = useState('ru');
  
  const handleTranslate = async () => {
    if (!inputText.trim()) return;
    
    setIsLoading(true);
    const result = await translateText(inputText, language);
    setTranslatedText(result || 'Translation failed');
    setIsLoading(false);
  };
  
  return (
    <div className="translation-widget">
      <div className="language-selector">
        <button 
          className={language === 'ru' ? 'active' : ''}
          onClick={() => setLanguage('ru')}
        >
          Uzbek → Russian
        </button>
        <button 
          className={language === 'uz' ? 'active' : ''}
          onClick={() => setLanguage('uz')}
        >
          Russian → Uzbek
        </button>
      </div>
      
      <textarea
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        placeholder={language === 'ru' ? "Matn kiriting..." : "Введите текст..."}
        className="input-textarea"
      />
      
      <button 
        onClick={handleTranslate}
        disabled={isLoading || !inputText.trim()}
        className="translate-button"
      >
        {isLoading ? 'Tarjima qilinyapti...' : 'Tarjima qilish'}
      </button>
      
      {translatedText && (
        <div className="translation-result">
          <h4>Tarjima:</h4>
          <p>{translatedText}</p>
        </div>
      )}
    </div>
  );
};
```

### Batch Translation
```javascript
const translateMultiple = async (phrases, targetLanguage) => {
  const translations = {};
  
  // Process in parallel for better performance
  const promises = phrases.map(async (phrase) => {
    const result = await translateText(phrase, targetLanguage);
    return { phrase, translation: result };
  });
  
  const results = await Promise.all(promises);
  
  results.forEach(({ phrase, translation }) => {
    translations[phrase] = translation;
  });
  
  return translations;
};

// Usage
const phrases = ["Salom", "Rahmat", "Xayr"];
const translations = await translateMultiple(phrases, "ru");
console.log(translations);
// { "Salom": "Привет", "Rahmat": "Спасибо", "Xayr": "Пока" }
```

## Performance Optimization

### Best Practices
1. **Debounce Input**: Wait for user to stop typing before translating
2. **Cache Locally**: Store frequent translations in app memory/storage
3. **Batch Requests**: Group multiple translations when possible
4. **Handle Errors**: Graceful fallback for network issues

### Rate Limiting Considerations
- OpenAI has rate limits based on your plan
- Consider implementing client-side debouncing
- Cache aggressively to reduce API calls
- Monitor usage through OpenAI dashboard

## Configuration Requirements

### Environment Variables
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### OpenAI Setup
1. Create account at [OpenAI Platform](https://platform.openai.com)
2. Generate API key in API settings
3. Add billing information for usage
4. Monitor usage in OpenAI dashboard

### Database Schema
The translation cache uses this table structure:
```sql
CREATE TABLE translations (
    id SERIAL PRIMARY KEY,
    input_text VARCHAR NOT NULL,
    target_language VARCHAR(2) NOT NULL,
    output_text VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(input_text, target_language)
);
```

## Monitoring and Analytics

### Useful Metrics
- **Translation requests per day**
- **Cache hit rate** (% of requests served from cache)
- **Average response time** (API vs cached)
- **Most translated phrases**
- **Language pair popularity**

### Cost Monitoring
- Track OpenAI API usage and costs
- Monitor cache effectiveness
- Optimize frequently used translations

This translation API provides a robust, scalable solution for Uzbek-Russian translation with intelligent caching and error handling, perfect for educational language learning applications.