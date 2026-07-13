"""YES24 IT 모바일 베스트셀러 도서 목록을 스크래핑하는 모듈.

이 모듈은 YES24의 베스트셀러 카테고리 페이지에서 데이터를 요청하고 파싱하여
도서 정보를 수집한 후, 그 결과를 CSV 파일로 저장하는 기능을 제공한다.
"""

import httpx
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
import sys

def clean_number(text: str) -> int:
    """텍스트에서 숫자만 추출하여 정수로 변환한다.

    Args:
        text: 숫자를 포함하고 있는 문자열.

    Returns:
        추출된 정수값. 텍스트가 비어있거나 숫자가 없으면 0을 반환한다.
    """
    if not text:
        return 0
    # 숫자만 추출
    num_str = re.sub(r'[^\d]', '', text)
    return int(num_str) if num_str else 0

def clean_float(text: str) -> float:
    """텍스트에서 실수를 추출하여 float으로 변환한다.

    Args:
        text: 실수를 포함하고 있는 문자열.

    Returns:
        추출된 실수값. 텍스트가 비어있거나 실수가 없으면 0.0을 반환한다.
    """
    if not text:
        return 0.0
    # 실수 형태만 추출
    float_match = re.search(r'\d+\.\d+|\d+', text)
    return float(float_match.group()) if float_match else 0.0

def scrape_yes24_bestsellers() -> None:
    """YES24 IT 모바일 종합 베스트셀러 목록의 전체 페이지를 수집하여 CSV로 저장한다.

    이 함수는 실제 브라우저와 유사한 요청 헤더를 구성하여 YES24에 요청을 보낸다.
    첫 페이지를 분석하여 전체 페이지 수를 확인한 후, 각 페이지의 도서 정보를
    BeautifulSoup으로 파싱하여 수집한다. 수집 완료 후 'yes24_it_bestseller.csv' 파일로 저장한다.

    Raises:
        SystemExit: 첫 페이지 요청이 실패하여 크롤링을 진행할 수 없는 경우.
    """
    base_url = "https://www.yes24.com/product/category/bestseller"
    category_number = "001001003" # IT 모바일 종합
    page_size = 24
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.yes24.com/',
    }
    
    print("YES24 IT 모바일 베스트셀러 크롤링을 시작합니다.")
    print("1페이지를 요청하여 전체 페이지 수를 확인 중...")
    
    # 1페이지 요청
    params = {
        'categoryNumber': category_number,
        'pageNumber': 1,
        'pageSize': page_size
    }
    
    try:
        response = httpx.get(base_url, headers=headers, params=params, timeout=10.0)
        response.raise_for_status()
    except Exception as e:
        print(f"1페이지 요청 실패: {e}")
        sys.exit(1)
        
    soup = BeautifulSoup(response.text, 'lxml')
    
    # 전체 페이지 수 구하기
    total_pages = 1
    end_page_elem = soup.select_one('div.yesUI_pagen a.bgYUI.end')
    if end_page_elem and end_page_elem.get('title'):
        try:
            total_pages = int(end_page_elem.get('title'))
        except ValueError:
            pass
    else:
        # '맨끝' 버튼이 없는 경우 숫자 링크들을 찾아 최대값을 구함
        page_links = soup.select('div.yesUI_pagen a.num')
        if page_links:
            page_nums = []
            for link in page_links:
                try:
                    page_nums.append(int(link.text.strip()))
                except ValueError:
                    pass
            if page_nums:
                total_pages = max(page_nums)
                
    print(f"감지된 전체 페이지 수: {total_pages} 페이지")
    
    all_books = []
    
    for page in range(1, total_pages + 1):
        print(f"\n[{page}/{total_pages}] 페이지 수집 중...")
        
        # 1페이지는 이미 요청한 결과를 활용
        if page == 1:
            page_soup = soup
        else:
            params['pageNumber'] = page
            # 차단 방지를 위한 지연시간 설정
            delay = random.uniform(0.8, 1.5)
            time.sleep(delay)
            
            try:
                response = httpx.get(base_url, headers=headers, params=params, timeout=10.0)
                response.raise_for_status()
                page_soup = BeautifulSoup(response.text, 'lxml')
            except Exception as e:
                print(f"[{page}페이지] 요청 실패. 건너뜁니다. 에러: {e}")
                continue
                
        # 도서 목록 파싱
        book_list = page_soup.select('ul#yesBestList > li')
        if not book_list:
            print(f"[{page}페이지] 도서 목록을 찾을 수 없습니다. (크롤링이 차단되었거나 페이지가 비어있을 수 있습니다)")
            break
            
        page_book_count = 0
        for li in book_list:
            try:
                # 1. 상품번호
                goods_no = li.get('data-goods-no', '').strip()
                if not goods_no:
                    continue
                
                # 2. 순위
                rank_elem = li.select_one('em.ico.rank')
                rank = clean_number(rank_elem.text) if rank_elem else 0
                
                # 3. 도서명
                title_elem = li.select_one('a.gd_name')
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                
                # 4. 부제목
                subtitle_elem = li.select_one('span.gd_nameE')
                subtitle = subtitle_elem.text.strip() if subtitle_elem else ""
                
                # 5. 저자
                author_elem = li.select_one('span.info_auth')
                author = author_elem.text.strip() if author_elem else ""
                # "저자 저" 등의 텍스트 정제 (끝에 ' 저' 또는 ' 등저'가 붙음)
                author = re.sub(r'\s+저$', '', author)
                author = re.sub(r'\s+등저$', '', author)
                
                # 6. 출판사
                pub_elem = li.select_one('span.info_pub')
                publisher = pub_elem.text.strip() if pub_elem else ""
                
                # 7. 출판일
                date_elem = li.select_one('span.info_date')
                pub_date = date_elem.text.strip() if date_elem else ""
                
                # 8. 판매가
                price_elem = li.select_one('strong.txt_num em.yes_b')
                sale_price = clean_number(price_elem.text) if price_elem else 0
                
                # 9. 정가(원가)
                orig_price_elem = li.select_one('span.txt_num.dash em.yes_m')
                original_price = clean_number(orig_price_elem.text) if orig_price_elem else sale_price
                
                # 10. 포인트
                point_elem = li.select_one('span.yPoint')
                point = clean_number(point_elem.text) if point_elem else 0
                
                # 11. 판매지수
                sale_index_elem = li.select_one('span.saleNum')
                sale_index = clean_number(sale_index_elem.text) if sale_index_elem else 0
                
                # 12. 평점
                rating_elem = li.select_one('span.rating_grade em.yes_b')
                rating = clean_float(rating_elem.text) if rating_elem else 0.0
                
                # 13. 리뷰 수
                review_elem = li.select_one('span.rating_rvCount em.txC_blue')
                review_count = clean_number(review_elem.text) if review_elem else 0
                
                book_info = {
                    '순위': rank,
                    '상품번호': goods_no,
                    '도서명': title,
                    '부제목': subtitle,
                    '저자': author,
                    '출판사': publisher,
                    '출판일': pub_date,
                    '판매가': sale_price,
                    '정가': original_price,
                    '적립포인트': point,
                    '판매지수': sale_index,
                    '평점': rating,
                    '리뷰수': review_count
                }
                
                all_books.append(book_info)
                page_book_count += 1
                
            except Exception as e:
                print(f"도서 파싱 중 에러 발생: {e}")
                continue
                
        print(f"-> {page}페이지에서 {page_book_count}개 도서 수집 완료")
        
        # 1페이지 결과로 너무 적은 도서가 파싱되었을 경우 차단 여부 의심
        if page == 1 and page_book_count == 0:
            print("첫 페이지 수집 실패. 스크래핑을 중단합니다.")
            break
            
    # CSV 저장
    if all_books:
        df = pd.DataFrame(all_books)
        # 순위 기준으로 정렬
        df = df.sort_values(by='순위').reset_index(drop=True)
        
        csv_filename = "yes24_it_bestseller.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"\n[완료] 총 {len(df)}개의 도서 정보를 수집하여 '{csv_filename}'에 저장했습니다.")
    else:
        print("\n수집된 도서 정보가 없습니다.")

if __name__ == "__main__":
    scrape_yes24_bestsellers()
