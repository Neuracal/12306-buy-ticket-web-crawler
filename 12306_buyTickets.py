import requests
import base64
import json
import re
import time
import pandas as pd
from PIL import Image  # 操作图片
import threading
import sys
import codecs
import datetime
from tabulate import tabulate
from urllib import parse

# 本程序主要参考https://www.tnblog.net/cz/article/details/162 和 https://www.tnblog.net/cz/article/details/241
# 以及《实战Python网络爬虫》，黄永祥著，第19章“实战：12306抢票爬虫”
# 两个链接的文章给予了大量代码方面的支持，它的实现似乎比黄永祥书的代码要好，但是也有参考书的代码
# 在分析url、网页请求的参数之找规律、推断网页请求的参数的意义、网页请求参数的意义解释方面，书给予了极大帮助

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
}
session.headers = headers
city_code_filepath = 'station_code.xlsx'

def get_url(url):
    request = session.get(url=url, headers=headers)
    request.encoding = 'UTF-8-SIG'
    return request.text

def post_url(url, data):
    header = { # 其实不用设置这个header也行，因为前面本程序前面已经指定过了
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    request = session.post(url=url, headers=header, data=data)
    return request.text

def getImage(img):
    filepath = './login.png'
    with open(filepath, 'wb') as fd:  # w写入 b二进制形式
        fd.write(img)
    return filepath

# 获取登录用的二维码
def getQR():
    data = post_url('https://kyfw.12306.cn/passport/web/create-qr64', data={"appid": "otn"})
    json_result = json.loads(data)
    if json_result['result_message'] == '生成二维码成功':
        login_pic = getImage(base64.b64decode(json_result['image']))
        # Image.open(login_pic).show() # 如果写了这句，好像要关掉弹出的图片窗口，程序才会继续进行下一句
        print("登录二维码login.png生成成功，请扫描...")
        return json_result['uuid']

# 检测二维码是否被扫描、是否已经登录成功
def checkQR(uuid):
    while 1:
        checkQR_url = 'https://kyfw.12306.cn/passport/web/checkqr'
        data = post_url(checkQR_url, data={'uuid': uuid, "appid": 'otn'})
        json_result = json.loads(data)
        # print(json_result)
        result_code = json_result['result_code']
        if result_code == '0':
            print('等待扫描')
        if result_code == '1':  # 已经扫描, json_result = {'result_message': '二维码状态查询成功', 'result_code': '1'}
            print('已扫描请确定')
        elif result_code == '2':  # 这个状态码表示手机上点击了登录, json_result = {'result_message': '扫码登录成功', 'uamtk': 'GHxDuBDiyoObn1_veKd5jiQZTMZiIatJwFVVY3pvfASyTCba09z1z0', 'result_code': '2'}
            print(json_result['result_message'], "已经登录")
            return
        elif result_code == '3':  # 此时'result_message'为“二维码已过期”
            new_uuid = getQR()
            if new_uuid:
                checkQR(new_uuid)
            return
        time.sleep(2)

# 检测用户是否已经登录
def check_login():
    # url1和url2的信息要用Fiddler才能看到，用Chrome的F12看不到；这两个url都可以在扫码登录中马上被抓包看见
    url1 = 'https://kyfw.12306.cn/passport/web/auth/uamtk' # 这个url返回是否登录成功
    data1 = {
        'appid': 'otn'
    }
    r1 = json.loads(post_url(url1, data1))
    if r1['result_message'] == "验证通过":
        newapptk = r1['newapptk']
        data2 = {
            'tk': newapptk
        }
        url2 = 'https://kyfw.12306.cn/otn/uamauthclient' # 这个url的作用是给出用户名
        r2 = json.loads(post_url(url2, data2))
        print("登录成功！\n用户名：", r2['username'])
        return True
    else:
        return False

# 储存cookie，以便之后不需要再扫码登录
def saveCookie():
    _cookies = session.cookies.get_dict()
    #取到session的cookie信息 取出来是键值对把他转化成字符串类型保存下来
    cookieStr = json.dumps(_cookies) 
    with open('./cookies.txt','w') as f:
        f.write(cookieStr)
        print('记录cookie成功')

# 读取cookie，为不需要扫码登录做准备
def getCookie():
    try:
        with open('./cookies.txt','r') as f: 
            _cookie = json.load(f)
            #session的cookie是一个RequestsCookieJar类型的，把键值对转换为给它
            session.cookies =requests.utils.cookiejar_from_dict(_cookie) 
    except FileNotFoundError: #
        print('还未登录过..')

# 将车站名和车站电报码转换
def load_city_code(filepath, method):
    df = pd.read_excel(filepath)
    if method=='name2code':
        data = df.set_index('station_name')['station_telecode'].to_dict()
    elif method=='code2name':
        data = df.set_index('station_telecode')['station_name'].to_dict()
    return data

# 查询车票
def train_info(train_date, from_station_name, to_station_name):
    from_station_code = city_dict[from_station_name]
    to_station_code = city_dict[to_station_name]
    # 购买成人票
    url = f'https://kyfw.12306.cn/otn/leftTicket/queryG?leftTicketDTO.train_date={train_date}&leftTicketDTO.from_station={from_station_code}&leftTicketDTO.to_station={to_station_code}&purpose_codes=ADULT'
    r = session.get(url, headers=headers)
    # print(r.url)
    with open("train_info.json", "w", encoding="utf-8") as json_file:
        json.dump(r.json(), json_file, ensure_ascii=False, indent=4)

    def translate_class_info(s):
        if s == '':
            s = '无'
        elif s == '无':
            s = '候补'
        return s

    data = []
    for entry in r.json()['data']['result']:
        train_info_status = entry.split('|')
        # train_info_status中各项的具体含义可以在https://kyfw.12306.cn/otn/confirmPassenger/initDc（这是一个html文件）中的第1748行找到
        row_data = {}
        if train_info_status[0]!='': #表示可以预订
            row_data['secretStr'] = train_info_status[0] # 这个字符串之后在订票中要用到
            row_data['train_no'] = train_info_status[2] # 车班号，如630000T1700W
            row_data['stationTrainCode'] = train_info_status[3] # 车次号，如G813
            row_data['origin_station'] = code_dict[train_info_status[4]] # 始发站名字
            row_data['terminal_station'] = code_dict[train_info_status[5]] # 终点站名字
            row_data['from_station'] = code_dict[train_info_status[6]] # 出发站名字
            row_data['to_station'] = code_dict[train_info_status[7]] # 到达站名字
            row_data['fromStationTelecode'] = train_info_status[6] # 出发站的代码
            row_data['toStationTelecode'] = train_info_status[7] # 到达站的代码
            row_data['departure_time'] = train_info_status[8] # 出发站出发时间
            row_data['arrival_time'] = train_info_status[9] # 到达站到达时间
            row_data['duration'] = train_info_status[10] # 历时（单位是hh:mm）
            row_data['leftTicket'] = train_info_status[12]
            row_data['second_class'] = translate_class_info(train_info_status[30]) # 二等座
            row_data['first_class'] = translate_class_info(train_info_status[31]) # 一等座
            row_data['business_class'] = translate_class_info(train_info_status[32]) # 商务座
            row_data['bed_level_info'] = train_info_status[53] # bed_level_info和seat_level_info在订票时用到
            row_data['seat_discount_info'] = train_info_status[54]
            data.append(row_data)
    df = pd.DataFrame(data)
    df.to_csv(f'train_info_{train_date}_{from_station_name}至{to_station_name}.csv', index=False, encoding='utf-8-sig')
    print("查询到的所有车次信息如下：")
    subdf = df[['stationTrainCode', 'from_station', 'to_station', 'departure_time', 'arrival_time', 'second_class', 'first_class', 'business_class']]
    subdf.rename(columns={
        'stationTrainCode': '列车号',
        'from_station': '出发站',
        'to_station': '到达站',
        'departure_time': '出发时间',
        'arrival_time': '到达时间',
        'second_class': '二等座',
        'first_class': '一等座',
        'business_class': '商务座'
    }, inplace=True)
    subdf.index = range(1, len(df) + 1) # 使得第一个车次的序号为1而不是0
    table_headers = ['序号'] + list(subdf.columns)
    print(tabulate(subdf, headers=table_headers, tablefmt="grid", numalign='center'))
    return df

# 预订车票
# train_info_df是从train_info函数中返回的Pandas DataFrame，idx表示在train_info_df中买第几个（从1开始算）列车的车票
def train_order(train_info_df, train_date, from_station_name, to_station_name):
    idx = input("请输入您要预订的车票是所查询到所有车次中的第几个车次（最上面的车次为第一个车次）：")
    idx = int(idx)
    back_train_date = datetime.datetime.now().strftime('%Y-%m-%d') # 获取当前日期
    url = 'https://kyfw.12306.cn/otn/leftTicket/submitOrderRequest'
    data = {
        'secretStr': parse.unquote(train_info_df.loc[idx-1, 'secretStr']), #要把原本的secretStr解析，即把%2B变成+等，然后再用POST请求订票
        'train_date': train_date,
        'back_train_date': back_train_date,
        'tour_flag': 'dc', # 表示“单程”，这里就不买往返票了
        'purpose_codes': 'ADULT', # 表示成人票，这里不买学生票等
        'query_from_station_name': from_station_name,
        'query_to_station_name': to_station_name,
        'bed_level_info': train_info_df.loc[idx-1, 'bed_level_info'],
        'seat_discount_info': train_info_df.loc[idx-1, 'seat_discount_info'],
        'undefined': ''
    }
    r = post_url(url, data=data)
    # print(r)
    if json.loads(r)['status']:
        print("预订成功，所预订的车票信息如下：")
    else:
        print("预订失败")
        return "预订失败"
    # 返回将要购买的车次的信息
    train_tobuy_info = {
        'train_date': train_date,
        'train_no': train_info_df.loc[idx-1, 'train_no'],
        'stationTrainCode': train_info_df.loc[idx-1, 'stationTrainCode'],
        'fromStationTelecode': train_info_df.loc[idx-1,'fromStationTelecode'],
        'toStationTelecode': train_info_df.loc[idx-1,'toStationTelecode'],
        'leftTicket': train_info_df.loc[idx-1,'leftTicket'],
    }
    print(f"列车号：{train_tobuy_info['stationTrainCode']}；出发日：{train_date}；时间：{train_info_df.loc[idx-1, 'departure_time']}-{train_info_df.loc[idx-1, 'arrival_time']}；从{from_station_name}到{to_station_name}。")
    return train_tobuy_info

# 提交和生成订单
#seat_class表明是“二等座”等等，train_tobuy_info是个储存车次号等信息的字典，choose_seats表示选择的座位号（如A、B），它为None时表示随机选择
def create_order(seat_class, train_tobuy_info, choose_seats=None):
    # 前面的函数是用于获得网页提交请求时的一些信息
    seat_classes = {
            "硬座": 1, # “硬座”等即seat_class
            "硬卧": 3,
            "软卧": 4,
            "商务座": 9,
            "一等座": 'M',
            "二等座": 'O'
        }
    def getinitDc():
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/initDc'
        data = {'_json_att': ''}
        html_data = post_url(url, data) # 返回一个html网页
        REPEAT_SUBMIT_TOKEN = re.findall(re.compile("var globalRepeatSubmitToken = '(.*?)';", re.S), html_data)[0]
        # 下面purpose_codes和train_loaction利用正则表达式匹配时可能返回空值，要多重新运行程序才有可能不是空值，这可能是12306随机反爬虫机制的体现
        purpose_codes = re.findall(re.compile(",'purpose_codes':'(.*?)',", re.S), html_data)[0]
        train_location = re.findall(re.compile(",'train_location':'(.*?)'", re.S), html_data)[0]
        key_check_isChange = re.findall(re.compile("'key_check_isChange':'(.*?)',", re.S), html_data)[0]
        json_initDc = {
            'REPEAT_SUBMIT_TOKEN': REPEAT_SUBMIT_TOKEN,
            'purpose_codes': purpose_codes,
            'train_location': train_location,
            'key_check_isChange': key_check_isChange
        }
        return json_initDc
    
    def getPassengerDTOs(REPEAT_SUBMIT_TOKEN):
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/getPassengerDTOs'
        data = {
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': REPEAT_SUBMIT_TOKEN
        }
        r = post_url(url, data)
        r = json.loads(r)
        passenger_info = {}
        names = [] # 储存所有乘车人姓名
        index = 0 # 需要购票的乘车人是第几个乘车人
        print("该账号下可以购票的乘车人有：")
        for item in r['data']['normal_passengers']:
            print(item['passenger_name'], end='\t')
            names.append(item['passenger_name'])
        name = input("\n请输入需要购票的乘车人姓名（只能输入一人）：")
        if name not in names:
            print(f"乘车人姓名输入错误，程序自动选择第一位乘车人：{names[0]}")
            name = names[0]
            index = 0
        else:
            index = names.index(name)
        passenger_info['name'] = name
        passenger_info['passenger_id_no'] = r['data']['normal_passengers'][index]['passenger_id_no']
        passenger_info['allEncStr'] = r['data']['normal_passengers'][index]['allEncStr']
        passenger_info['passenger_id_type_code'] = r['data']['normal_passengers'][index]['passenger_id_type_code']
        passenger_info['mobile_no'] = r['data']['normal_passengers'][index]['mobile_no']
        return passenger_info

    # 提交订单时有两个请求：checkOrderInfo和getQueueCount    
    def checkOrderInfo(passenger_info, REPEAT_SUBMIT_TOKEN):
        passenger_info['passengerTicketStr'] = seat_classes[seat_class] + ",0" + ",1," + passenger_info['name'] + "," + passenger_info['passenger_id_type_code'] + "," + passenger_info['passenger_id_no'] + "," + passenger_info['mobile_no'] + ",N," + passenger_info['allEncStr']
        passenger_info['oldPassengerStr'] = passenger_info['name'] + "," + passenger_info['passenger_id_type_code'] + "," + passenger_info['passenger_id_no'] + ",1_"
        # 仅购买成人票
        data = {
            'cancel_flag': 2,
            'bed_level_order_num': '000000000000000000000000000000',
            'passengerTicketStr': passenger_info['passengerTicketStr'],
            'oldPassengerStr': passenger_info['oldPassengerStr'],
            'tour_flag': 'dc',
            'whatsSelect': 1,
            'sessionId': '',
            'sig': '',
            'scene': 'nc_login',
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': REPEAT_SUBMIT_TOKEN
        }
        return data

    def getQueueCount(json_initDc):
        data = {
            'train_date': time.strftime("%a %b %d %Y 00:00:00 GMT+0800", time.strptime(train_tobuy_info['train_date'], "%Y-%m-%d"))+' (中国标准时间)',
            'train_no': train_tobuy_info['train_no'],
            'stationTrainCode': train_tobuy_info['stationTrainCode'],
            'seatType': seat_classes[seat_class],
            'fromStationTelecode': train_tobuy_info['fromStationTelecode'],
            'toStationTelecode': train_tobuy_info['toStationTelecode'],
            'leftTicket': train_tobuy_info['leftTicket'],
            'purpose_codes': json_initDc['purpose_codes'],
            'train_location': json_initDc['train_location'],
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': json_initDc['REPEAT_SUBMIT_TOKEN']
        }
        return data
    
    # 生成订单
    def confirmSingleForQueue(passenger_info, json_initDc):
        data = {
            'passengerTicketStr': passenger_info['passengerTicketStr'],
            'oldPassengerStr': passenger_info['oldPassengerStr'],
            'purpose_codes': json_initDc['purpose_codes'],
            'key_check_isChange': json_initDc['key_check_isChange'],
            'leftTicketStr': train_tobuy_info['leftTicket'],
            'train_location': json_initDc['train_location'],
            'choose_seats': f'1{choose_seats}', # 默认选择A座位
            'seatDetailType': '000',
            'is_jy': 'N',
            'is_cj': 'Y',
            'encryptedData': '',
            'whatsSelect': '1',
            'roomType': '00',
            'dwAll': 'N',
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': json_initDc['REPEAT_SUBMIT_TOKEN']
        }
        if choose_seats is None:
            data['choose_seats'] = '' # 为空则网站随机选择座位
        return data
    
    def queryOrderWaitTime(json_initDc):
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/queryOrderWaitTime?random='+str(int(time.time()*1000))+'&tourFlag=dc&_json_att=&REPEAT_SUBMIT_TOKEN='+json_initDc['REPEAT_SUBMIT_TOKEN']
        r = get_url(url)
        r = json.loads(r)
        orderId = ''
        if r['status'] and r['data']['queryOrderWaitTimeStatus']:
            print('正在生成订单，请稍候...')
            orderId = r['data']['orderId'] # 订单号，一开始可能还未生成，所以要用while循环等待其生成
            loop_count = 0
            while orderId is None: # python没有do while循环，所以这里while循环重写了上面的语句
                time.sleep(0.5)
                r = json.loads(get_url(url))
                if r['status'] and r['data']['queryOrderWaitTimeStatus']:
                    orderId = r['data']['orderId']
                loop_count = loop_count + 1
                # print("in while")
                if loop_count > 20: # 不要循环访问太多次
                    print("生成订单失败，错误信息：", r)
                    return
            return orderId
        else:
            print("生成订单失败，错误信息：", r[['messages']])
    
    # 生成订单后会弹出init?random=时间戳界面，这个html文件有许多可以用的信息
    def initRandom():
        url = 'https://kyfw.12306.cn/otn/payOrder/init?random=' + str(int(time.time()*1000))
        html_data = get_url(url)
        parOrderDTOJson = re.findall(re.compile("var parOrderDTOJson = '(.*?)';", re.S), html_data)[0]
        parOrderDTOJson = codecs.decode(parOrderDTOJson, 'unicode_escape')
        parOrderDTOJson = json.loads(parOrderDTOJson)
        stationTrainDTOJson = parOrderDTOJson['orders'][0]['tickets'][0]['stationTrainDTO']
        passengerDTOJson = parOrderDTOJson['orders'][0]['tickets'][0]['passengerDTO']
        ticketsJson = parOrderDTOJson['orders'][0]['tickets'][0]

        pay_info = {
            'ticket_price': f"{parOrderDTOJson['ticket_price_all']/100:.2f}元",
            'ticket_totalnum': parOrderDTOJson['orders'][0]['ticket_totalnum'],
            'station_train_code': stationTrainDTOJson['station_train_code'],
            'from_station_name': stationTrainDTOJson['from_station_name'],
            'to_station_name': stationTrainDTOJson['to_station_name'],
            'start_time': stationTrainDTOJson['start_time'].split(' ')[1][:5], # 出发时间mm:ss，如06:20
            'arrive_time': stationTrainDTOJson['arrive_time'].split(' ')[1][:5],
            'passenger_name': passengerDTOJson['passenger_name'],
            'passenger_id_type_name': passengerDTOJson['passenger_id_type_name'],
            'passenger_id_no': passengerDTOJson['passenger_id_no'],
            'mobile_no': passengerDTOJson['mobile_no'],
            'coach_name': ticketsJson['coach_name'],
            'seat_name': ticketsJson['seat_name'], # 席位号
            'seat_type_name': ticketsJson['seat_type_name'], # 如二等座
            'ticket_type_name': ticketsJson['ticket_type_name'], # 成人票
            'train_date_str': ticketsJson['train_date_str'] # 列车出发时间所在的日期，如2025-03-19
        }
        return pay_info
    
    # 生成订单
    def resultOrderForDcQueue(orderId, REPEAT_SUBMIT_TOKEN):
        data = {
            'orderSequence_no': orderId,
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': REPEAT_SUBMIT_TOKEN
        }
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/resultOrderForDcQueue'
        r = post_url(url, data)
        r = json.loads(r)
        if r['status'] and r['data']['submitStatus']:
            print("下单成功！订单信息如下：")
            pay_info = initRandom()
            print(f"{pay_info['train_date_str']}\t{pay_info['station_train_code']}次\t{pay_info['from_station_name']}站 ({pay_info['start_time']}开) --- {pay_info['to_station_name']} ({pay_info['arrive_time']}到)")
            subdf = {
                "姓名": pay_info['passenger_name'],
                "证件类型": pay_info['passenger_id_type_name'],
                "证件号码": pay_info['passenger_id_no'],
                "手机号": pay_info['mobile_no'],
                "票种": pay_info['ticket_type_name'],
                "席别": pay_info['seat_type_name'],
                "车厢": pay_info['coach_name'],
                "席位号": pay_info['seat_name'],
                "票价 (元)": pay_info['ticket_price']
            }
            subdf = pd.DataFrame([subdf])
            print(tabulate(subdf, headers="keys", tablefmt="grid", showindex=False, numalign='center'))
            print("请在10分钟内在12306手机端或者网页端付款~")
        else:
            print("下单失败，错误信息：", r['messages'])

    json_initDc = getinitDc()
    passenger_info = getPassengerDTOs(json_initDc['REPEAT_SUBMIT_TOKEN'])
    r_checkOrderInfo = post_url('https://kyfw.12306.cn/otn/confirmPassenger/checkOrderInfo', checkOrderInfo(passenger_info, json_initDc['REPEAT_SUBMIT_TOKEN']))
    r_getQueueCount = post_url('https://kyfw.12306.cn/otn/confirmPassenger/getQueueCount', getQueueCount(json_initDc))
    r_checkOrderInfo = json.loads(r_checkOrderInfo)
    r_getQueueCount = json.loads(r_getQueueCount)
    remaining_tickets = r_getQueueCount['data']['ticket']
    remaining_seat_class_tickets, remaining_no_seat_tickets, remaining_tickets_str = None, None, None
    # 如果有无座票，那么remaining_tickets的格式如“125,311”，125个二等座票，311个无座票；如果没有无座票，那么remaining_tickets为125，没有逗号
    if ',' in remaining_tickets:
        remaining_tickets = remaining_tickets.split(',')
        remaining_seat_class_tickets = remaining_tickets[0]
        remaining_no_seat_tickets = remaining_tickets[1]
        remaining_tickets_str = f"{seat_class}余票{remaining_seat_class_tickets}张，无座余票{remaining_no_seat_tickets}张"
    else:
        remaining_tickets_str = f"{seat_class}余票{remaining_tickets}张"
    if r_getQueueCount['status']:
        print(f"提交下单成功，{remaining_tickets_str}，排队人数{r_getQueueCount['data']['count']}人。")
        if r_getQueueCount['data']['op_2'] == 'true': # 这表示排队人数超过余票
            print('排队人数超过余票')
    else:
        print("提交下单信息失败，错误信息：", r_getQueueCount['messages'])
        return
    r_confirmSingleForQueue = post_url('https://kyfw.12306.cn/otn/confirmPassenger/confirmSingleForQueue', confirmSingleForQueue(passenger_info, json_initDc))
    r_confirmSingleForQueue = json.loads(r_confirmSingleForQueue)
    if r_confirmSingleForQueue['status'] and r_confirmSingleForQueue['data']['submitStatus']:
        print("选座成功！")
    else:
        print('选座失败，错误信息：', r_confirmSingleForQueue['messages'])
        return
    orderId = queryOrderWaitTime(json_initDc)
    resultOrderForDcQueue(orderId, json_initDc['REPEAT_SUBMIT_TOKEN'])


if __name__ == "__main__":
    getCookie()
    if not check_login():
        uuid = getQR()
        if uuid:
            check_thread = threading.Thread(target=checkQR, args=(uuid,))
            check_thread.start()
            check_thread.join()
            saveCookie()
        if not check_login():
            print("登录失败，请重新启动程序，扫码登录")
            sys.exit(1)
    city_dict = load_city_code(city_code_filepath, 'name2code') # 根据车站名找到对应的电报码
    code_dict = load_city_code(city_code_filepath, 'code2name') # 根据电报码找到对应的车站名
    # 下面这几个变量可以用input与用户交互，不过这里为了方便测试就没有这样做
    # seat_class是座位等级，本程序只支持一等座、二等座、商务座；choose_seats是选择座位号，如A, B, C, D, F，没有E，有些列车或者一等座时一排的座位比5个少，所以建议该变量写成None，则网页会随机指定座位
    train_date,  from_station_name, to_station_name, seat_class, choose_seats = '2025-03-20', '长沙', '合肥', '二等座', None
    
    # 开始买票，生成订单
    train_info_df = train_info(train_date, from_station_name, to_station_name)
    train_tobuy_info = train_order(train_info_df, train_date, from_station_name, to_station_name)
    create_order(seat_class, train_tobuy_info, choose_seats)