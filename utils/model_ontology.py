model_ontology = {
    "기계설비부문_난방기기": { # GUI name of the section
        "key": "tbl_nanbangkiki", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "설명": "설명",
            "난방급탕구분": "구분",
            "열생산기기방식": "난방방식",
            "연결된시스템": "연결된신재생",
            "사용연료": "사용연료",
            "보일러정격출력": "기기용량(kW)",
            "보일러대수": "기기대수",
            "정격보일러효율" : "기기효율(%)",
            "정격보일러COP" : "성적계수(COP)",
            "펌프동력": "펌프동력합계(kW)",
        }
    },
    "기계설비부문_냉방기기": {
        "key": "tbl_nangbangkiki",
        "columns": {
            "code": "code",
            "설명": "설명",
            "냉동기방식": "냉방방식",
            "냉동기용량": "용량(kW)",
            "대수": "기기대수",
            "열성능비": "열성능비(COP)",
            "냉동기종류": "냉동기종류",
            "연결된시스템": "연결된신재생",
            "사용연료": "사용연료",
            "냉수펌프동력": "냉수펌프동력(kW)",
            "증발식건식냉각기": "냉각탑종류",
            "냉각수펌프동력": "냉각수펌프동력",
        }
    },
    "건축부문_외피": { # GUI name of the section
        "key": "tbl_myoun", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "설명": "설명",
            "열관류율2": "형별성능내역",
            "방위": "방위",
            "건축부위면적": "면적(m²)",
            "수평차양각": "수평차양각(°)",
            "수직차양각": "수직차양각(°)",
            "면형태": "부위",
        }
    },
    "건축부문_외피_형별성능내역": { # GUI name of the section
        "key": "tbl_yk", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "설명": "설명",
            "면형태": "부위",
            "바닥난방여부": "바닥난방여부",
            "열교방지구조": "열교방지구조",
            "창호열관류율": "창호열관류율",
            "일사에너지투과율": "일사에너지투과율(-)",
            "열관류율": "열관류율(W/m²K)", # 계산값
        }
    },
    "건축부문_외피_형별성능내역_재료": { # GUI name of the section
        "key": "tbl_ykdetail", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "pcode": "형별성능내역",
            "code": "형별성능내역 구성 순번",
            "설명": "재료명",
            "열전도율": "열전도율(W/mK)",
            "두께": "두께(mm)",
            "커스텀": "열전도율 및 두께 커스텀 입력 여부",
            "열저항": "열저항(m²K/W)", # 계산값
        }
    },
    "설비부문_공조기기": { # GUI name of the section
        "key": "tbl_kongjo", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "설명": "설명",
            "공조방식": "공조방식",
            "대수": "대수",
            "설정치난방": "난방급기온도(°C)",
            "설정치냉방": "냉방급기온도(°C)",
            "급기풍량": "급기풍량(CMH)",
            "배기풍량": "배기풍량(CMH)",
            "총압력손실급기팬": "급기정압(Pa)",
            "총압력손실배기팬": "배기정압(Pa)",
            "급기팬동력": "급기팬동력(kW)",
            "배기팬동력": "배기팬동력(kW)",
            "열교환기유형": "열교환기유형",
            "열회수율": "난방열회수율(%)",
            "열회수율_냉방": "냉방열회수율(%)",
        }
    },
    "설비부문_조명기기": { # GUI name of the section
        "key": "tbl_light", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "설명": "설명",
            "조명종류": "조명기기종류",
            "조명전력": "조명전력(W)",
            "대수": "대수",
        }
    },
    "설비부문_실내단말기": { # GUI name of the section
        "key": "tbl_danmal", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "설명": "설명",
            "용량": "용량(kW)",
            "팬동력": "팬동력(W)",
            "대수": "대수",
        }
    },
    "건축부문_층별개요": { # GUI name of the section
        "key": "tbl_type", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "층": "설명",
            "면적": "면적",
            "시설용도": "허가용도",
        }
    },
    "건축부문_기본개요": { # GUI name of the section
        "key": "tbl_Desc", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "buildm21": "지하층면적(m²)",
            "buildm23": "지상층면적(m²)",
            "builds1": "지하층수",
            "builds2": "지상층수",
            "층고": "층고(m)",
            "천장고": "천장고(m)",
        }
    },
    "일반부문": { # GUI name of the section
        "key": "tbl_Desc", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "건축물명칭": "건축물명칭",
            "buildarea": "지역",
            "민간구분": "공공민간구분",
        }
    },
    "신재생에너지설비부문_태양광": { # GUI name of the section
        "key": "tbl_new_light", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "설명": "설명",
            "태양광용량": "용량(kW)",
            "태양광모듈면적": "모듈면적(m²)",
            "태양광모듈기울기": "모듈기울기",
            "태양광모듈방위": "모듈방위",
            "태양광모듈종류": "모듈종류",
            "태양광모듈효율": "모듈효율(%)",
            "태양광모듈적용타입": "모듈타입",
        }
    },
    "신재생에너지설비부문_태양열": { # GUI name of the section
        "key": "tbl_new_energy", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "설명": "설명",
            "태양열종류": "시스템구분",
            "집열기유형": "집열기유형",
            "집열판면적": "면적(m²)",
            "집열판방위": "방위",
            "집열효율": "집열효율(-)",
            "솔라펌프의정격출력": "솔라펌프동력(W)",
            "축열탱크체적급탕": "급탕탱크체적(L)",
            "축열탱크체적난방": "난방탱크체적(L)",
            "축열탱크설치장소": "축열탱크설치장소",
        }
    },
    "신재생에너지설비부문_지열": { # GUI name of the section
        "key": "tbl_new_ground", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "설명": "설명",
            "가동연료": "가동연료",
            "지열냉난방구분": "냉난방구분",
            "지열히트펌프용량": "지열히트펌프용량(kW)",
            "열성능비난방": "열성능비난방(COP,난방)",
            "열성능비냉방": "열성능비냉방(COP,냉방)",
            "펌프용량1차": "지중순환펌프동력(W)",
        }
    },
    "신재생에너지설비부문_열병합발전": { # GUI name of the section
        "key": "tbl_new_열병합", # XML key of the section
        "columns": {
            # XML key of the field -> GUI name of the field
            "code": "code",
            "설명": "설명",
            "열병합냉난방구분": "냉난방구분",
            "열생산능력": "열생산능력(kW)",
            "열생산효율": "열생산효율(%)",
            "발전효율": "발전효율(%)",
            "열병합신재생여부": "열병합신재생여부",
        }
    },
}