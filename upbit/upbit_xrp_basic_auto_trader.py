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

access_key = 'UPBIT_OPEN_API_ACCESS_KEY'
secret_key = 'UPBIT_OPEN_API_SECRET_KEY'
server_url = 'https://api.upbit.com'

hold_xrp_amount = 0.0             # 보유한 XRP 개수
taret_hold_xrp_amount = 12.0      # 구매할 XPP 개수
xrp_buy_price = None              # 매수한 XRP 금액
target_take_profit_ratio = 0.01   # 1%
target_stop_loss_ratio = -0.01    # -1%
trade_ended = False               # 트레이딩 종료 유무 판단


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
    
    async with websockets.connect(uri,  ping_interval=60) as websocket:
        global hold_xrp_amount
        global xrp_buy_price
        global trade_ended

        subscribe_fmt = [
                {"ticket":"test"},
                {
                "type": "ticker",
                "codes":["KRW-XRP"],
                "isOnlyRealtime": True
                },
                {"format":"SIMPLE"}
            ]

        subscribe_data = json.dumps(subscribe_fmt)
        await websocket.send(subscribe_data)
            
        while True:
            data = await websocket.recv()
            data = json.loads(data)

            current_time = datetime.datetime.fromtimestamp(data['tms']/1000)
            current_price = float(data['tp'])

            # 매수한 물량이 없으면 매수
            if trade_ended == False and hold_xrp_amount < taret_hold_xrp_amount:
                # 시장가 매수
                result = buy_market_order(market_buy_amt=(taret_hold_xrp_amount+1)*current_price, coin_name='XRP')
                print(f'{current_time} 시장가 매수 주문! order_id : {result["uuid"]}, 보유 XRP 개수 : {hold_xrp_amount}')
                time.sleep(0.1)

                # 잔고확인 API를 통한 XRP 보유 개수 확인 & XRP 구매 금액 확인
                result = get_balance()
                for each_asset in result:
                    if each_asset['currency'] == 'XRP':
                        hold_xrp_amount = float(each_asset['balance'])
                        xrp_buy_price = float(each_asset['avg_buy_price'])
                time.sleep(0.1)

            # 매 Websocket 수신마다 정보 확인
            if trade_ended == False:
                print(f'현재시간 : {current_time}, XRP 현재가 : {current_price}, 매수가대비 차이 : {((current_price/xrp_buy_price)-1)*100:.2f}%')
            elif trade_ended == True:
                print('거래 완료')

            # 익절조건 만족 확인
            if trade_ended == False and ((current_price/xrp_buy_price)-1) > target_take_profit_ratio:
                print('+++++++++++++++++++++++++++++++++++ 익절 조건 만족 +++++++++++++++++++++++++++++++++++++++++')
                result = sell_market_order(coin_name='XRP', market_sell_amt=hold_xrp_amount)
                print(f'{current_time} 시장가 매도 주문! order_id : {result["uuid"]}')
                trade_ended = True
                time.sleep(0.1)

            # 손절조건 만족 확인
            if trade_ended == False and ((current_price/xrp_buy_price)-1) < target_stop_loss_ratio:
                print('----------------------------------- 손절 조건 만족 -----------------------------------------')
                result = sell_market_order(coin_name='XRP', market_sell_amt=hold_xrp_amount)
                print(f'{current_time} 시장가 매도 주문! order_id : {result["uuid"]}')
                trade_ended = True
                time.sleep(0.1)

async def main():
    await upbit_ws_client()

if __name__ == "__main__":
    # 잔고확인 API를 통한 XRP 보유 개수 확인 & XRP 구매 금액 확인
    result = get_balance()
    for each_asset in result:
        if each_asset['currency'] == 'XRP':
            hold_xrp_amount = float(each_asset['balance'])
            print("XRP 보유 개수 :", hold_xrp_amount)
            xrp_buy_price = float(each_asset['avg_buy_price'])
            print("XRP 구매 단가 :", xrp_buy_price)

    # 메인 loop 실행
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())