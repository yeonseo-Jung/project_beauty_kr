# necessary
import os
import time
import pandas as pd
from datetime import datetime

# db connection 
import pymysql
import sqlalchemy

class AccessDataBase:
    
    def __init__(self, user_name, password, db_name):
        # user info & db
        self.user_name = user_name
        self.password = password
        self.db_name = db_name
    
        # today 
        today = datetime.today()
        year = str(today.year)
        month = str(today.month)
        day = str(today.day)
        if len(month) == 1:
            month = "0" + month
        if len(day) == 1:
            day = "0" + day    
        self.date = year[2:4] + month + day
        self.regist_date = year + "-" + month + "-" + day
        
    def db_connect(self):
        ''' db connect '''

        host_url = "db.ds.mycelebs.com"
        port_num = 3306
        conn = pymysql.connect(host=host_url, user=self.user_name, passwd=self.password, port=port_num, db=self.db_name, charset='utf8')
        curs = conn.cursor(pymysql.cursors.DictCursor)
        return conn, curs
    
    def insert(self, table: str, fields: tuple, values: tuple) -> None:
        _fields = ''
        for field in fields:
            if _fields == '':
                _fields +=  field
            else:
                _fields += ', ' + field
        _fields_ = '(' + _fields + ')'

        conn, curs = self.db_connect()

        query = f"INSERT INTO `{table}`{_fields_} VALUES{str(values)};"
        curs.execute(query)

        conn.commit()
        curs.close()
        conn.close()

    def get_tbl_name(self):
        ''' db에 존재하는 모든 테이블 이름 가져오기 '''

        conn, curs = self.db_connect()

        # get table name list
        query = "SHOW TABLES;"
        curs.execute(query)
        tables = curs.fetchall()

        table_list = []
        for table in tables:
            tbl = list(table.values())[0]
            table_list.append(tbl)
        
        curs.close()
        conn.close()
        
        return table_list

    def get_tbl_columns(self, table_name):
        ''' 선택한 테이블 컬럼 가져오기 '''
        
        conn, curs = self.db_connect()

        # get table columns 
        query = f"SHOW FULL COLUMNS FROM {table_name};"
        curs.execute(query)
        columns = curs.fetchall()

        column_list = []
        for column in columns:
            field = column['Field']
            column_list.append(field)
        
        curs.close()
        conn.close()
        
        return column_list

    def get_tbl(self, table_name, columns='all'):
        ''' db에서 원하는 테이블, 컬럼 pd.DataFrame에 할당 '''
        
        if table_name in self.get_tbl_name():
            st = time.time()
            conn, curs = self.db_connect()
            
            if columns == 'all':
                query = f'SELECT * FROM {table_name};'
            else:
                # SELECT columns
                query = 'SELECT '
                i = 0
                for col in columns:
                    if i == 0:
                        query += f"`{col}`"
                    else:
                        query += ', ' + f"`{col}`"
                    i += 1

                # FROM table_name
                query += f' FROM {table_name};'
            curs.execute(query)
            tbl = curs.fetchall()
            df = pd.DataFrame(tbl)
            curs.close()
            conn.close()
            
            ed = time.time()
            print(f'`{table_name}` Import Time: {round(ed-st, 1)}sec\n\n')
        else:
            df = None
            print(f'\n\n{table_name} does not exist in db')
        
        return df
    
    def integ_tbl(self, table_name_list, columns):
        ''' 
        db에서 컬럼이 같은 여러개 테이블 가져오기
        db에서 테이블 가져온 후 데이터 프레임 통합 (concat)
        '''

        df = pd.DataFrame()
        for tbl in table_name_list:
            df_ = self.get_tbl(tbl, columns)
            df_.loc[:, 'table_name'] = tbl
            df = pd.concat([df, df_])
        df = df.reset_index(drop=True)
        return df

    def sqlcol(self, dfparam):    
        ''' Convert DataFrame data type to sql data type '''
        
        dtypedict = {}
        for i,j in zip(dfparam.columns, dfparam.dtypes):
            
            if "object" in str(j):
                dtypedict.update({i: sqlalchemy.types.NVARCHAR(length=255)})
                                    
            if "datetime" in str(j):
                dtypedict.update({i: sqlalchemy.types.DateTime()})

            if "float" in str(j):
                dtypedict.update({i: sqlalchemy.types.Float(precision=3, asdecimal=True)})

            if "int" in str(j):
                dtypedict.update({i: sqlalchemy.types.INT()})

        return dtypedict

    def engine_upload(self, upload_df, table_name, if_exists_option, pk=None):
        ''' Upload Table into DB '''
        
        host_url = "db.ds.mycelebs.com"
        port_num = 3306
        
        # engine
        engine = sqlalchemy.create_engine(f'mysql+pymysql://{self.user_name}:{self.password}@{host_url}:{port_num}/{self.db_name}?charset=utf8mb4')
        
        # Create table or Replace table 
        upload_df.to_sql(table_name, engine, if_exists=if_exists_option, index=False)
        
        # Setting pk 
        if pk != None:
            engine.execute(f'ALTER TABLE {table_name} ADD PRIMARY KEY (`{pk}`);')
        else:
            pass
        
        engine.dispose()
        print(f'\nTable Upload Success: {table_name}')
                
    def table_update(self, table_name, pk, df):
        ''' Table Update from DB
        
        table_name: table name from db
        pk: primary key
        df: dataframe to update 
        
        '''
        try:
            # get table from db
            _df = self.get_tbl(table_name, 'all')
                    
            # 기존에 존재하는 status값 update
            df_update = _df.loc[:, [pk]].merge(df, on=pk, how='inner')

            # 새로운 status값 append
            df_dedup = pd.concat([_df, df]).drop_duplicates(subset=pk, keep=False)
            df_append = pd.concat([df_update, df_dedup]).sort_values(by=pk).reset_index(drop=True)
            
            self.engine_upload(df_append, table_name, "replace", pk=pk)
            
        except Exception as e:
            # 신규 테이블 업로드
            print(e)
            df = df.sort_values(by=pk).reset_index(drop=True)
            self.engine_upload(df, table_name, "replace", pk=pk)
            
    def table_backup(self, table_name):
        
        conn, curs = self.db_connect()
        
        table_list = self.get_tbl_name()
        if table_name in table_list:
            new_table_name = f'{table_name}_backup_{self.date}'
            
            # 백업 테이블이 이미 존재하는경우 replace(drop -> insert)
            if new_table_name in table_list:
                curs.execute(f'DROP TABLE {new_table_name};')
                
            query = f'ALTER TABLE {table_name} RENAME {new_table_name};'
            curs.execute(query)
        else:
            pass
        
        conn.commit()
        curs.close()
        conn.close()
        
    def create_table(self, upload_df, table_name):
        ''' Create table '''
        
        if 'info_all' in table_name:
            category = table_name.replace('beauty_kr_', '').replace('_info_all', '')
        elif 'reviews_all' in table_name:
            category = table_name.replace('beauty_kr_', '').replace('_reviews_all', '')
        else:
            category = ""
            
        query_dict = {
            'beauty_kr_mapping_table': "CREATE TABLE beauty_kr_mapping_table (\
                                        `item_key` int(11) DEFAULT NULL COMMENT '매핑 기준 상품 id',\
                                        `item_keep_words` varchar(255) DEFAULT NULL COMMENT '매핑 기준 상품 세부정보',\
                                        `mapped_id` int(11) DEFAULT NULL COMMENT '매핑 대상 상품 id',\
                                        `mapped_keep_words` varchar(255) DEFAULT NULL COMMENT '매핑 대상 상품 세부정보',\
                                        `source` varchar(255) DEFAULT NULL COMMENT '매핑 대상 상품 소스 테이블명'\
                                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8;",
                                        
            f'beauty_kr_{category}_info_all': f"CREATE TABLE `beauty_kr_{category}_info_all` (\
                                                `item_key` int(11) DEFAULT NULL COMMENT '매핑 기준 상품 id',\
                                                `product_url` text COMMENT '상품 url',\
                                                `product_store` text COMMENT '상품 판매 스토어',\
                                                `product_store_url` text COMMENT '스토어 별 판매 링크',\
                                                `product_price` varchar(255) COMMENT '스토어 별 판매 가격',\
                                                `delivery_fee` varchar(255) COMMENT '스토어 별 배송비',\
                                                `naver_pay` varchar(255) COMMENT '네이버페이 유무',\
                                                `product_status` int(11) DEFAULT NULL COMMENT '상품 판매 상태 (1: 판매중, 0: 판매중단)',\
                                                `page_status` int(11) DEFAULT NULL COMMENT '상품 판매 페이지 상태 (1: 네이버 뷰티윈도 가격비교 탭, 2: 네이버 뷰티윈도 전체 탭, -1: 페이지 누락)',\
                                                `product_code` int(11) DEFAULT NULL,\
                                                `product_name` varchar(255),\
                                                `brand_code` int(11),\
                                                `brand_name` varchar(255),\
                                                `product_url_glowpick` text,\
                                                `selection` varchar(255),\
                                                `division` varchar(255),\
                                                `groups` varchar(255),\
                                                `descriptions` text,\
                                                `product_keywords` varchar(255),\
                                                `color_type` varchar(255),\
                                                `volume` varchar(255),\
                                                `image_source` text,\
                                                `ingredients_all_kor` text,\
                                                `ingredients_all_eng` text,\
                                                `ingredients_all_desc` text,\
                                                `ranks` varchar(255),\
                                                `product_awards` text,\
                                                `product_awards_sector` text,\
                                                `product_awards_rank` text,\
                                                `price` varchar(255) COMMENT '정가',\
                                                `product_stores` varchar(255) COMMENT '글로우픽 기준 판매 스토어',\
                                                `status` int(11) COMMENT '단종 여부 (0: 단종, 1: 판매중)',\
                                                `dup_check` int(11) COMMENT '중복 여부 (0: 단일상품(중복x), -1: 종속상품(중복o), 1: 대표상품(중복o))',\
                                                `dup_id` varchar(255) COMMENT '종속상품 id 리스트',\
                                                `regist_date` datetime DEFAULT NULL COMMENT '개체 수집 일자',\
                                                `category` varchar (255) DEFAULT NULL COMMENT '카테고리'\
                                                ) ENGINE=InnoDB DEFAULT CHARSET=utf8;",
                                                
            f'beauty_kr_{category}_reviews_all': f"CREATE TABLE `beauty_kr_{category}_reviews_all` (\
                                                    `pk` int(11) unsigned NOT NULL AUTO_INCREMENT,\
                                                    `item_key` int(11) DEFAULT NULL COMMENT '매핑 기준 상품 id',\
                                                    `txt_data` text COMMENT '리뷰 데이터',\
                                                    `write_date` text COMMENT '리뷰 작성일자',\
                                                    `regist_date` text COMMENT '데이터 업로드 일자',\
                                                    `source` text COMMENT '데이터 출처 테이블 명',\
                                                    PRIMARY KEY (`pk`)\
                                                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;",
            
            'glowpick_product_info_final_version': f"CREATE TABLE `glowpick_product_info_final_version` (\
                                                    `id` int(11) DEFAULT NULL COMMENT '상품 아이디 (자체부여)',\
                                                    `product_code` int(11) DEFAULT NULL COMMENT '글로우픽 내부 상품 코드',\
                                                    `product_name` varchar(255),\
                                                    `brand_code` int(11),\
                                                    `brand_name` varchar(255),\
                                                    `product_url` varchar(255),\
                                                    `selection` varchar(255),\
                                                    `division` varchar(255),\
                                                    `groups` varchar(255),\
                                                    `descriptions` text,\
                                                    `product_keywords` varchar(255),\
                                                    `color_type` varchar(255),\
                                                    `volume` varchar(255),\
                                                    `image_source` text,\
                                                    `ingredients_all_kor` text,\
                                                    `ingredients_all_eng` text,\
                                                    `ingredients_all_desc` text,\
                                                    `ranks` varchar(255),\
                                                    `product_awards` text,\
                                                    `product_awards_sector` text,\
                                                    `product_awards_rank` text,\
                                                    `price` varchar(255) COMMENT '정가',\
                                                    `product_stores` varchar(255) COMMENT '글로우픽 기준 판매 스토어',\
                                                    `status` int(11) COMMENT '단종 여부 (0: 단종, 1: 판매중)',\
                                                    `dup_check` int(11) COMMENT '중복 여부 (0: 단일상품(중복x), -1: 종속상품(중복o), 1: 대표상품(중복o))',\
                                                    `dup_id` varchar(255) COMMENT '종속상품 id 리스트'\
                                                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;",
                                                
            'glowpick_product_info_final_version_review': f"CREATE TABLE glowpick_product_info_final_version_review (\
                                                            `id` int(11) DEFAULT NULL COMMENT '싱품 id',\
                                                            `product_code` int(11) DEFAULT NULL COMMENT '글로우픽 내부 상품 코드',\
                                                            `user_id` varchar(100) DEFAULT NULL COMMENT '유저 아이디',\
                                                            `product_rating` int(11) DEFAULT NULL COMMENT '상품 평점',\
                                                            `review_date` varchar(100) DEFAULT NULL COMMENT '리뷰 작성 일자',\
                                                            `product_review` text DEFAULT NULL COMMENT '리뷰 내용'\
                                                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8;",
                                                            
            'oliveyoung_product_info_final_version': f"CREATE TABLE `oliveyoung_product_info_final_version` (\
                                                        `id` int(11) NOT NULL,\
                                                        `product_code` varchar(100) DEFAULT NULL,\
                                                        `product_name` varchar(100) DEFAULT NULL,\
                                                        `product_url` varchar(255) DEFAULT NULL,\
                                                        `brand_name` varchar(100) DEFAULT NULL,\
                                                        `price` int(11) DEFAULT NULL,\
                                                        `sale_price` int(11) DEFAULT NULL,\
                                                        `selection` varchar(100) DEFAULT NULL,\
                                                        `division` varchar(100) DEFAULT NULL,\
                                                        `groups` varchar(100) DEFAULT NULL,\
                                                        `brand_code` varchar(100) DEFAULT NULL,\
                                                        `brand_url` varchar(100) DEFAULT NULL,\
                                                        `product_rating` float DEFAULT NULL,\
                                                        `product_size` varchar(100) DEFAULT NULL,\
                                                        `skin_type` varchar(100) DEFAULT NULL,\
                                                        `expiration_date` varchar(100) DEFAULT NULL,\
                                                        `how_to_use` text,\
                                                        `manufacturer` varchar(100) DEFAULT NULL,\
                                                        `manufactured_country` varchar(100) DEFAULT NULL,\
                                                        `ingredients_all` text,\
                                                        `status` int(11) DEFAULT NULL\
                                                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8;",
                                                        
            'oliveyoung_product_info_final_version_review': f"CREATE TABLE `oliveyoung_product_info_final_version_review` (\
                                                                `pk` int(11) unsigned NOT NULL AUTO_INCREMENT,\
                                                                `id` int(11) NOT NULL,\
                                                                `product_code` varchar(100) DEFAULT NULL,\
                                                                `product_url` varchar(255) DEFAULT NULL,\
                                                                `user_id` varchar(100) DEFAULT NULL,\
                                                                `product_rating` int(11) DEFAULT NULL,\
                                                                `review_date` datetime DEFAULT NULL,\
                                                                `product_review` text NOT NULL,\
                                                                PRIMARY KEY (`pk`),\
                                                                KEY `id` (`id`)\
                                                                ) ENGINE=InnoDB DEFAULT CHARSET=utf8;"
        }
        
        if 'info_all' in table_name:
            query = query_dict[f'beauty_kr_{category}_info_all']
        elif 'reviews_all' in table_name:
            query = query_dict[f'beauty_kr_{category}_reviews_all']
        else:
            if table_name in list(query_dict.keys()):
                query = query_dict[table_name]
            else:
                query = None
        
        if query == None:
            print('query is None')
        else:
            # backup table
            self.table_backup(table_name)
            
            # create table
            conn, curs = self.db_connect()
            curs.execute(query)
            
            # upload table
            self.engine_upload(upload_df, table_name, if_exists_option='append')
            
            # drop temporary table
            table_list = self.get_tbl_name()
            if  f'{table_name}_temp' in table_list:
                curs.execute(f'DROP TABLE {table_name}_temp;')
            
            # commit & close
            conn.commit()
            curs.close()
            conn.close()