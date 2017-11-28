from requests import HTTPError

from api import API
from repository import Repository
from utility import log, log_dict


class User:
    def __init__(self, node):
        self.name = node['name']
        self.login = node['login']
        self.url = node['url']
        r1 = node['pinnedRepositories']['edges']
        r2 = node['repositories']['edges']

        if len(r1) == 0:
            r = Repository.repositories_from_nodes(r2)
        else:
            r = Repository.repositories_from_nodes(r1)

        self.repositories = list(r)
        self.pinned_repositories = r1
        self.popular_repositories = r2
        self.contribution = []

    def __repr__(self):
        classname = self.__class__.__name__
        properties = ['{}: ({})'.format(k, v) for k, v in self.__dict__.items()]
        s = '\n'.join(properties)
        return '< {}\n{} \n>\n'.format(classname, s)

    @classmethod
    def users_from_nodes(cls, nodes):
        for node in nodes:
            log('users_from_nodes')
            log_dict(node)
            n = node['node']
            yield User(n)

    def add_contribution(self):
        for r in self.repositories:
            q = Repository.query_for_contributors(r.name_with_owner)
            try:
                cs = API.get_v3(q)
            except HTTPError:
                cs = []
            total_commit = 0
            contributed_commit = 0
            for c in cs:
                login = c['author']['login']
                total = c['total']
                total_commit += total
                if login == self.login:
                    contributed_commit = total
            self.contribution.append((contributed_commit, total_commit, r.url))

    @staticmethod
    def query_china_user():
        r1 = Repository.query_pinned()
        r2 = Repository.query_popular()
        q = """
            {{
                search(first: 100, query: "location:china", type: USER) {{
                    edges {{
                        node {{
                            ... on User {{
                            login
                            name
                            url
                            {0}
                            {1}
                            }}
                        }}
                    }}
                }}
            }}
            """.format(r1, r2)
        return q