import pickle, base64

if __name__ == '__main__':

    dict = {
        '1':{
            'count':2,
            'selected':True
        }
    }

    # result = pickle.dumps(dict)
    # print(result)
    #
    # # result1 = pickle.loads(result)
    # # print(result1)
    #
    # res = base64.b64encode(result).decode()
    # print(res)

    result = base64.b64encode(pickle.dumps(dict)).decode()
    print(result)

    pickle.loads(base64.b64decode(result.encode()))

    # 简写:
    result2 = pickle.loads(base64.b64decode(result))
    print(result2)
