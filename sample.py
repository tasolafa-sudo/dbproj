def sample(how_many, max_num):
 list = []
 retry = 0
 while len(list) < how_many:
        randint = random.randint(0, max_num)
        if randint not in list:
            list.append(randint)
        else:
            retry + 1
 return list,retry

if name == 'main':
 print(sample(10, 100))