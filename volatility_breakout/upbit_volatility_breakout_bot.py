import websockets
import asyncio 
import json
import datetime
import jwt
import uuid
import hashlib
from urllib.parse import urlencode
import requests
import time
import telegram


access_key = 'UPBIT_OPEN_API_ACCESS_KEY'
secret_key = 'UPBIT_OPEN_API_SECRET_KEY'
server_url = 'https://api.upbit.com'

TELEGRAM_BOT_TOKEN = 'your_telegram_bot_token'
TELEGRAM_CHAT_ID = 'your_chat_id'

# 설정값 변수 설정
yesterday_high_price = None      # 전일 종가
yesterday_low_price = None       # 전일 저가
today_open_price = None          # 당일 시가
has_position = False             # 암호화폐 보유 유무
avg_buy_price = None             # 평균 매수 가격
has_candle_update = False        # 캔들 업데이트 유무
hold_position_amount = None      # 암호화폐 보유량
ticker = 'BTC'                   # 구매할 암호화폐
k_ratio = 0.5                    # range에 곱할 k값
target_buy_amount = 10000        # 목표 매수 금액
verbose = False                  # 디버깅용 정보 출력유무

# 일별 캔들 정보 조회
def get_day_candle(coin_name='XRP', payment_currency='KRW', count=200):
    query = {
        'market': f'{payment_currency}-{coin_name}',
        'count': str(count)
    }
    query_string = urlencode(query)

    url = "https://api.upbit.com/v1/candles/days?"+query_string

    headers = {"Accept": "application/json"}
    res = requests.get(url, headers=headers)

    return res.json()

# 보유 잔고 확인
def get_balance():
    payload = {
        'access_key': access_key,
        'nonce': str(uuid.uuid4()),
    }

    jwt_token = jwt.encode(payload, secret_key)
    authorize_token = 'Bearer {}'.format(jwt_token)
    headers = {"Authorization": authorize_token}

    res = requests.get(server_url + "/v1/accounts", headers=headers)

    return res.json()

# 시장가 매수 주문
def buy_market_order(market_buy_amt, coin_name='XRP', payment_currency='KRW'):
    query = {
        'market': f'{payment_currency}-{coin_name}',
        'side': 'bid',
        'price': str(market_buy_amt),
        'ord_type': 'price'
    }
    query_string = urlencode(query).encode()

    m = hashlib.sha512()
    m.update(query_string)
    query_hash = m.hexdigest()

    payload = {
        'access_key': access_key,
        'nonce': str(uuid.uuid4()),
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512',
    }

    jwt_token = jwt.encode(payload, secret_key)
    authorize_token = 'Bearer {}'.format(jwt_token)
    headers = {"Authorization": authorize_token}

    res = requests.post(server_url + "/v1/orders", params=query, headers=headers)

    return res.json()

# 시장가 매도 주문
def sell_market_order(market_sell_amt, coin_name='XRP', payment_currency='KRW'):
    query = {
        'market': f'{payment_currency}-{coin_name}',
        'side': 'ask',
        'volume': str(market_sell_amt),
        'ord_type': 'market'
    }
    query_string = urlencode(query).encode()

    m = hashlib.sha512()
    m.update(query_string)
    query_hash = m.hexdigest()

    payload = {
        'access_key': access_key,
        'nonce': str(uuid.uuid4()),
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512',
    }

    jwt_token = jwt.encode(payload, secret_key)
    authorize_token = 'Bearer {}'.format(jwt_token)
    headers = {"Authorization": authorize_token}

    res = requests.post(server_url + "/v1/orders", params=query, headers=headers)

    return res.json()

async def upbit_ws_client():
    uri = "wss://api.upbit.com/websocket/v1"
    
    websocket = await websockets.connect(uri, ping_interval=None)

    global has_position
    global avg_buy_price
    global hold_position_amount
    global today_open_price
    global yesterday_high_price
    global yesterday_low_price
    global has_candle_update

    subscribe_fmt = [
            {"ticket":"test"},
            {
            "type": "ticker",
            "codes":[f"KRW-{ticker}"],
            "isOnlyRealtime": True
            },
            {"format":"SIMPLE"}
        ]

    subscribe_data = json.dumps(subscribe_fmt)
    await websocket.send(subscribe_data)

    while True:
        try:
            data = await websocket.recv()
            data = json.loads(data)

            current_time = str(datetime.datetime.fromtimestamp(data['tms']/1000)).split(' ')[1]
            current_price = float(data['tp'])

            current_hour = current_time[:2]
            current_minute = current_time[3:5]

            # 디버깅용 정보 출력
            if verbose == True:
                print(f'current_hour : {current_hour}, current_minute : {current_minute}, target_buy_price : {(today_open_price + k_ratio * (yesterday_high_price - yesterday_low_price))}, current_price : {current_price}')

            # 9시 1분이 되면 만약 매수한 내역이 있으면 보유중인 암호화폐를 매도
            if current_hour == '09' and current_minute == '01':
                if has_position == True:
                    print(f'+++++++++++++++++++++++++++++++++++ sell {ticker} +++++++++++++++++++++++++++++++++++++++++')
                    sell_market_order_result = sell_market_order(coin_name=ticker, market_sell_amt=hold_position_amount)
                    print(f'{current_time} market sell ! order_id : {sell_market_order_result["uuid"]}')
                    has_position = False
                    time.sleep(0.1)

                    telegram_message_list = [str(datetime.datetime.now()), f'------------- sell {ticker} ----------']
                    telegram_bot.sendMessage(chat_id=TELEGRAM_CHAT_ID, text=' '.join(telegram_message_list))

                # 캔들 봉을 갱신하지 않았으면 캔들 봉 갱신
                if has_candle_update == False:
                    # 일(Day) 캔들 확인
                    get_day_candle_result = get_day_candle(coin_name=ticker, count=2)
                    # 가장 최근일 캔들 정보
                    today_open_price = float(get_day_candle_result[0]['opening_price'])
                    # 하루전 캔들 정보
                    yesterday_high_price = float(get_day_candle_result[1]['high_price'])
                    yesterday_low_price = float(get_day_candle_result[1]['low_price'])
                    print(f'@@@@@@@ candle update {str(datetime.datetime.now())} target_price: {(today_open_price + k_ratio * (yesterday_high_price - yesterday_low_price))} @@@@@@@@@@')
                    has_candle_update = True

                    telegram_message_list = [str(datetime.datetime.now()), f'@@@@@@@ candle update {ticker} target_price: {(today_open_price + k_ratio * (yesterday_high_price - yesterday_low_price))} @@@@@@@@@@@@@']
                    telegram_bot.sendMessage(chat_id=TELEGRAM_CHAT_ID, text=' '.join(telegram_message_list))
            else:
                # 변동성 돌파 전략 매수 조건 만족시 매수
                if has_position == False and current_price > (today_open_price + k_ratio * (yesterday_high_price - yesterday_low_price)):
                    # 시장가 매수
                    print(f'+++++++++++ buy {ticker} target_price: {(today_open_price + k_ratio * (yesterday_high_price - yesterday_low_price))} ++++++++++++++++++++++++++')
                    buy_market_order_result = buy_market_order(market_buy_amt=target_buy_amount, coin_name=ticker)
                    print(f'{current_time} market buy ! order_id : {buy_market_order_result["uuid"]}')
                    has_position = True
                    time.sleep(0.1)

                    # 잔고확인 API를 통한 암호화폐 보유 개수 확인 & 암호화폐 구매 금액 확인
                    get_balance_result = get_balance()
                    for each_asset in get_balance_result:
                        if each_asset['currency'] == ticker:
                            hold_position_amount = float(each_asset['balance'])
                            print(f"{ticker} 보유 개수 :", hold_position_amount)
                            avg_buy_price = float(each_asset['avg_buy_price'])
                            print(f"{ticker} 구매 단가 :", avg_buy_price)

                    telegram_message_list = [str(datetime.datetime.now()), f'------------- buy {ticker} ----------']
                    telegram_bot.sendMessage(chat_id=TELEGRAM_CHAT_ID, text=' '.join(telegram_message_list))

            # 9시 2분부터 다시 캔들봉 갱신 flag를 False로 변경
            if current_hour == '09' and current_minute == '02':
                has_candle_update = False
        except Exception as excep:
            print(ticker)
            print(excep)
            # 웹소켓 연결이 끊어졌을 경우에 재연결
            if not websocket.open:
                # 재연결
                websocket = await websockets.connect(uri, ping_interval=None)

                subscribe_fmt = [
                        {"ticket":"test"},
                        {
                        "type": "ticker",
                        "codes": [f"KRW-{ticker}"],
                        "isOnlyRealtime": True
                        },
                        {"format":"SIMPLE"}
                    ]

                subscribe_data = json.dumps(subscribe_fmt)
                await websocket.send(subscribe_data)

async def main():
    await upbit_ws_client()

if __name__ == "__main__":
    # set telegram bot
    telegram_bot = telegram.Bot(TELEGRAM_BOT_TOKEN)

    telegram_message_list = [str(datetime.datetime.now()), 'Program Started!']
    telegram_bot.sendMessage(chat_id=TELEGRAM_CHAT_ID, text=' '.join(telegram_message_list))

    # 잔고확인 API를 통한 암호화폐 보유 개수 확인 & 암호화폐 구매 금액 확인
    get_balance_result = get_balance()
    for each_asset in get_balance_result:
        if each_asset['currency'] == ticker:
            hold_position_amount = float(each_asset['balance'])
            print(f"{ticker} 보유 개수 :", hold_position_amount)
            avg_buy_price = float(each_asset['avg_buy_price'])
            print(f"{ticker} 구매 단가 :", avg_buy_price)
            if (hold_position_amount * avg_buy_price) > 1000:
                has_position = True

    # 캔들정보 확인
    # 일(Day) 캔들 확인
    get_day_candle_result = get_day_candle(coin_name=ticker, count=2)
    # 가장 최근일 캔들 정보
    today_open_price = float(get_day_candle_result[0]['opening_price'])
    # 하루전 캔들 정보
    yesterday_high_price = float(get_day_candle_result[1]['high_price'])
    yesterday_low_price = float(get_day_candle_result[1]['low_price'])

    # 메인 loop 실행
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())