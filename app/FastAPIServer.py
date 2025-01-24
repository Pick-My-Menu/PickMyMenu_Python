import urllib.request
import json
import os
import time
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import urllib.parse
from bs4 import BeautifulSoup
import google.generativeai as genai
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse, JSONResponse
from PIL import Image
from io import BytesIO

load_dotenv()

api_key = os.getenv("API_KEY")

model = genai.GenerativeModel(model_name="gemini-1.5-flash")
genai.configure(api_key=api_key)

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인에서 접근 가능
    allow_credentials=True,
    allow_methods=["*"],  # 모든 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

@app.get("/search")
async def search_blog(text: str = '', lat: str = '', lon: str = ''):
    print("------------시작------------")
    print("------", text)

    # 입력값 + "맛집"
    query = text + " 맛집"

    # 내 위치의 위도, 경도를 주소로 변환
    address = (lat, lon)
    geoloc = Nominatim(user_agent='South Korea', timeout=None)
    add = geoloc.reverse(address)
    if add is None:
        return JSONResponse(content={"error": "위치를 찾을 수 없습니다."}, status_code=400)
    print(add)

    # 기본 URL
    baseUrl = 'https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query='

    # URL 인코딩
    encoded_query = urllib.parse.quote(query)

    # 최종 URL
    url = baseUrl + encoded_query

    print(url)

    # 크롤링 결과를 담을 리스트
    all_blog_data = []

    # 페이지 HTML 요청
    html = urllib.request.urlopen(url).read()

    # BeautifulSoup 객체로 파싱
    soup = BeautifulSoup(html, 'html.parser')

    # 블로그 항목 추출
    blog_items = soup.find_all('li', class_='bx')

    # 각 블로그 정보 추출
    for item in blog_items:
        # 블로그의 제목, URL, 작성자, 작성 시간 추출
        title_tag = item.find('a', class_='title_link')
        title = title_tag.text.strip() if title_tag else "제목 없음"
        blog_url = title_tag['href'] if title_tag else "URL 없음"

        author_name = item.find('a', class_='name')
        author_name = author_name.text.strip() if author_name else "작성자 없음"

        author_time = item.find('span', class_='sub')
        author_time = author_time.text.strip() if author_time else "시간 없음"

        dsc_name_tag = item.find('a', class_='dsc_link')
        description = dsc_name_tag.text.strip() if dsc_name_tag else "설명 없음"

        # 이미지 URL 추출
        thumb_items = item.find_all('div', class_='thumb_item')
        image_urls = []

        for thumb_item in thumb_items:
            img_tag = thumb_item.find('a').find('img')
            if img_tag and img_tag.has_attr('src'):
                image_urls.append(img_tag['src'])

        # 최대 5개의 이미지 URL만 추출
        image_urls = image_urls[:5]

        blog_data = {
            "title": title,
            "url": blog_url,
            "author": author_name,
            "time": author_time,
            "description": description,
        }

        # 이미지 URL들을 image1, image2, ... 형태로 추가
        for i, image_url in enumerate(image_urls):
            blog_data[f"image{i+1}"] = image_url

        # 데이터 리스트에 추가
        all_blog_data.append(blog_data)

    # '없음' 값이 있는 항목을 필터링하는 함수
    def filter_empty_values(data):
        filtered_data = []
        for item in data:
            # '없음' 값이 있는 항목 제외
            filtered_item = {key: value for key, value in item.items() if value != "제목 없음" and value != "URL 없음" and value != "작성자 없음" and value != "시간 없음" and value != "설명 없음"}
            # 내용이 하나라도 남은 항목만 리스트에 추가
            if filtered_item:
                filtered_data.append(filtered_item)
        return filtered_data

    # '없음' 값을 필터링한 데이터
    filtered_data = filter_empty_values(all_blog_data)

    print("크롤링 완료")

    # gemini 모델에 전달할 질문 생성
    print("gemini 질문 시작")
    prompt = f"제공된 자료 : {filtered_data} , 제공된 자료중 15개만 추출해줘. title 만 title : '' 형식으로 반환해줘."
    chat_session = model.start_chat()
    response = chat_session.send_message(prompt)

    result = response.text[7:-4]

    print("gemini 응답 완료")

    data = json.loads(result)

    # 각 title을 변수로 저장
    titles = [item["title"] for item in data]

    # 출력 확인
    for i, title in enumerate(titles, start=1):
        globals()[f"title_{i}"] = title

    titles_to_keep = [globals()[f"title_{i}"] for i in range(1, 16)]
    filtered_data_to_keep = [data for data in filtered_data if data['title'] in titles_to_keep]


    print("필터링된 값 반환")
    print(filtered_data_to_keep)


    # os.remove(filename)
    # print(f"{filename} 삭제 완료.")

    return filtered_data_to_keep

@app.get("/upload")
async def upload_form():
    content = """
    <html>
        <body>
            <h2>이미지 업로드</h2>
            <form action="/image" method="post" enctype="multipart/form-data">
                <input type="file" name="file"/>
                <button type="submit">이미지 처리</button>
            </form>
        </body>
    </html>
    """
    return HTMLResponse(content=content)


@app.post("/image")
async def process_image(
        file: UploadFile = File(...),  # 업로드된 파일
        placeName: str = Form(...),  # 장소 이름
        phone: str = Form(...),  # 전화번호
        address: str = Form(...),  # 주소
        roadAddress: str = Form(...),  # 도로명 주소
):

    try:
        # 업로드된 파일을 메모리에서 처리
        image_data = await file.read()
        img = Image.open(BytesIO(image_data))

        # Google Generative AI API 호출
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")

        # 결과를 JSON 형태로 반환
        resInfo = {
            "placeName": placeName,
            "phone": phone,
            "address": address,
            "roadAddress": roadAddress,
        }
        response_content = json.dumps(resInfo, ensure_ascii=False)

        response = model.generate_content(["image : ",img, "data : ",response_content,
                                           "1. 이미지에 있는 키워드를 추출한다. "
                                           "2. 제공된 데이터에 이미지에서 추출한 키워드가 하나라도 포함되어있는지 판단한다. (ex 상호명, 주소)"
                                           "3. 왜 그렇게 판단했는지 간단하게 이유를 설명한다."
                                           "4. 포함되었다면 yes, 포함되지 않았다면 no라고 대답한다. 나머지에 대한 답변은 한글로 한다."])

        result = response.text
        print(result)

        stripResult = response.text.strip()  # 결과 문자열 가져오기 및 공백 제거

        if "yes" in stripResult.lower():  # 대소문자 구분 없이 체크
            return True
        elif "no" in stripResult.lower():
            return False
        else:
            return False  # 예상하지 못한 결과일 경우 False 처리

    except Exception as e:
        # 예외 발생 시 False 반환
        print(f"Error occurred: {str(e)}")  # 예외 내용을 로그로 출력
        return False  # 예외 발생 시 False 반환