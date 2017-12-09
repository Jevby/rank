import datetime
import json
import time

import requests
from sqlalchemy import (
    Column,
    String,
    Integer,
)

from source.exception import (
    NotExist,
    ErrorCode,
    ErrorCode202,
    ErrorCode451,
    GraphQLError,
)
from misc import (
    secret,
    config,
)
from source.database import Database
from source.utility import (
    log,
    log_error,
    ensure_not_none,
)


class API(Database.base):
    __tablename__ = 'api'
    query = Column(String, primary_key=True)
    response = Column(String)
    unixtime = Column(Integer)

    @classmethod
    def _get(cls, query):
        log('get result for query', query)
        m = Database.session.query(API).filter(API.query == query).scalar()
        if m is None:
            log('query not exist')
            raise NotExist
        else:
            return m

    @classmethod
    def _valid_cache(cls, m):
        now = int(time.time())
        t = now - m.unixtime
        if t < config.cache_time:
            return True
        else:
            return False

    @classmethod
    def _set(cls, query, response):
        log('set result for query', query)
        now = int(time.time())
        c = API(
            query=query,
            response=response,
            unixtime=now,
        )
        Database.session.merge(c)
        Database.session.commit()

    @classmethod
    def _check_rate_v4(cls, response):
        rate_limit = response['data']['rateLimit']
        limit = rate_limit['limit']
        remaining = rate_limit['remaining']
        cost = rate_limit['cost']
        reset_at = rate_limit['resetAt']
        log('v4 rate limit <{}> remaing <{}> cost <{}> resetAt <{}>'.format(
            limit, remaining, cost, reset_at)
        )
        time_format = '%Y-%m-%dT%H:%M:%SZ'
        reset_at = int(datetime.datetime.strptime(reset_at, time_format).timestamp())
        now = int(time.time())
        log('v4 rate will reset in <{}>'.format(reset_at - now))

        # don't knwo when rate will be 0, so compare with 3
        if remaining < 3:
            log('v4 no rate remaing')
            # sleep 5 seconds more to guarantee success
            time.sleep(5 + (reset_at - now))
            log('v4 finish sleep')

    @classmethod
    def _get_v4(cls, query):
        full_query = f"""
        {{
            rateLimit {{
                limit
                cost
                remaining
                resetAt
            }}
            {query}
        }}
        """
        url = 'https://api.github.com/graphql'
        json_query = {
            'query': full_query
        }
        headers = {'Authorization': 'bearer {}'.format(secret.token)}
        r = requests.post(url=url, json=json_query, headers=headers)

        if r.status_code == 200:
            j = r.json()
            ensure_not_none(j, f'query <{query}> result is <{j}>')
            if 'errors' in j:
                raise GraphQLError(j['errors'])
            else:
                cls._set(query, r.text)
                cls._check_rate_v4(j)
                return j
        else:
            raise ErrorCode(r.status_code, query)

    @classmethod
    def query_for_connection(cls, keyword, parameter, node):
        parameter_string = ""
        for k, v in parameter.items():
            # type is enum, so no double quote
            if type(v) is str and k != 'type':
                parameter_string += f'{k}: "{v}" '
            else:
                parameter_string += f'{k}: {v} '

        q = f"""
            {keyword}({parameter_string}) {{
                pageInfo {{
                  endCursor
                  hasNextPage
                  hasPreviousPage
                  startCursor
                }}
                edges {{
                    node {{
                        {node}
                    }}
                }}
            }}
        """
        return q

    @classmethod
    def _get_v4_cache(cls, query):
        try:
            m = cls._get(query)
        except NotExist:
            return cls._get_v4(query)
        else:
            if cls._valid_cache(m):
                return json.loads(m.response)
            else:
                return cls._get_v4(query)

    @classmethod
    def get_v4_connection(cls, keyword, parameter, node, first, count):
        parameter['first'] = first
        q = cls.query_for_connection(keyword, parameter, node)
        r = cls._get_v4_cache(q)
        s = r['data'][keyword]
        nodes = s['edges']
        yield from nodes
        end_cursor = s['pageInfo']['endCursor']

        steps = count // first
        for i in range(steps - 1):
            parameter['after'] = end_cursor
            q = cls.query_for_connection(keyword, parameter, node)
            r = cls._get_v4_cache(q)
            s = r['data'][keyword]
            nodes = s['edges']
            yield from nodes
            end_cursor = s['pageInfo']['endCursor']
            has_next_page = s['pageInfo']['hasNextPage']
            if end_cursor is None or not has_next_page:
                break

    @classmethod
    def get_v4_object(cls, query):
        return cls._get_v4_cache(query)

    @classmethod
    def _check_rate_v3(cls, response):
        rate_limit = int(response.headers['X-RateLimit-Limit'])
        rate_reset = int(response.headers['X-RateLimit-Reset'])
        rate_remaing = int(response.headers['X-RateLimit-Remaining'])
        log('v3 rate limit <{}> rate remaing <{}>'.format(rate_limit, rate_remaing))
        now = int(time.time())
        log('v3 rate will reset in <{}>'.format(rate_reset - now))

        if rate_remaing < 3:
            log('v3 no rate remaing')
            # sleep 5 seconds more to guarantee success
            time.sleep(5 + (rate_reset - now))
            log('v3 finish sleep and try again')

    @classmethod
    def _get_v3(cls, query):
        base = 'https://api.github.com'
        url = '{}{}'.format(base, query)
        log('get v3 url', url)
        headers = {'Authorization': 'bearer {}'.format(secret.token)}
        r = requests.get(url=url, headers=headers)

        if r.status_code == 200:
            log('get v3 r', r)
            j = r.json()
            ensure_not_none(j, f'query <{query}> result is <{j}>')
            cls._set(query, r.text)
            cls._check_rate_v3(r)
            return j
        elif r.status_code == 202:
            raise ErrorCode202(202, query)
        # don't knwo when rate will be 0, so compare with 3
        else:
            raise ErrorCode(r.status_code, query)

    @classmethod
    def get_v3(cls, query):
        try:
            m = cls._get(query)
        except NotExist:
            try:
                cls._get_v3(query)
            except ErrorCode202:
                time.sleep(5)
                cls._get_v3(query)
        else:
            if cls._valid_cache(m):
                r = json.loads(m.response)
                return r
            else:
                try:
                    return cls._get_v3(query)
                except ErrorCode202:
                    r = json.loads(m.response)
                    return r

    @classmethod
    def _get_crawler(cls, query):
        base = 'https://github.com'
        url = '{}{}'.format(base, query)
        log('get crawler url', url)
        agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " \
                "AppleWebKit/537.36 (KHTML, like Gecko) " \
                "Chrome/62.0.3202.94 Safari/537.36"
        headers = {'User-Agent': agent}
        r = requests.get(url=url, headers=headers)
        if r.status_code == 200:
            html = r.text
            cls._set(query, html)
            return html
        elif r.status_code == 451:
            raise ErrorCode451(451, query)
        else:
            raise ErrorCode(r.status_code, query)

    @classmethod
    def get_crawler(cls, query):
        try:
            m = cls._get(query)
        except NotExist:
            return cls._get_crawler(query)
        else:
            if cls._valid_cache(m):
                return m.response
            else:
                return cls._get_crawler(query)
