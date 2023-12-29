import requests
from bs4 import BeautifulSoup
import pandas as pd

def scrape_traffic_data(data_id):
    session = requests.Session()
    headers = {
        'authority': 'txdot.public.ms2soft.com',
        'accept': '*/*',
        'accept-language': 'en,zh;q=0.9,zh-CN;q=0.8,ja;q=0.7,zh-TW;q=0.6',
        'referer': 'https://txdot.public.ms2soft.com/tcds/tdetail.asp?updatemap=&from_map=',
        'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    }
    response_list = []

    try:
        # Perform an initial request to get cookies
        home_response = session.get('https://txdot.public.ms2soft.com/tcds/tsearch.asp', headers=headers)
        cks = home_response.cookies

        for pg in range(1, 6):  # Assuming there are at most 5 pages
            params = {
                'offset': '0',
                'agency_id': '97',
                'local_id': data_id,
                'page_type': '',
                'pg': str(pg),
            }

            response = session.get(
                'https://txdot.public.ms2soft.com/tcds/ajax/tcds_tdetail_aadt.asp',
                params=params,
                headers=headers,
                cookies=cks
            )

            response_list.append(response.text)

        return response_list

    except Exception as e:
        print(f"Error: {e}")
        return None

def process_data(response_list):
    col_names = []
    row_data = []
    for response in response_list:
        soup = BeautifulSoup(response, 'html.parser')
        rows_tr = soup.find_all('tr', class_='FormRowLabel')

        # Getting column names
        if not col_names:
            col_names = [cell.text.strip() for cell in rows_tr[0] if cell.text.strip()]

        # Getting values by rows
        for i in range(1, len(rows_tr)):
            row = rows_tr[i].find_all('td')
            if len(row) <= 1:
                break
            cell_data = [cell_bs.text for cell_bs in row if cell_bs.text != '']
            row_data.append(cell_data)
            
    return col_names, row_data
    

def main():
    data_id = '15H193'  # You can change this to any desired data_id
    response_list = scrape_traffic_data(data_id)

    if response_list:
        col_names, row_data = process_data(response_list)

    # Create a DataFrame from the extracted data and save as a csv file
    df = pd.DataFrame(row_data, columns=col_names)
    df.to_csv(f'historical_aadt_{data_id}.csv', index=False)  
    print('Data saved as csv file')
        
        

if __name__ == "__main__":
    main()
