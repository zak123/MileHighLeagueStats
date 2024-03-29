import headers as h
from graphqlclient import GraphQLClient
import pandas as p
import json as j
import time


score_map = {
    1: 100,
    2: 50,
    3: 25,
    4: 12,
    5: 6,
    7: 3
}


# total entrants
def get_total_entrants() -> int:
    client = GraphQLClient('https://api.start.gg/gql/' + h.__APIversion__)
    client.inject_token('Bearer ' + h.__token__)
    event_list = client.execute(h.__top8_query__, h.__top8_vars__)
    entrants = j.loads(event_list)['data']['tournament']['events'][0]['numEntrants']

    return entrants


# different find top 8
def get_top_8() -> p.DataFrame:
    client = GraphQLClient('https://api.start.gg/gql/' + h.__APIversion__)
    client.inject_token('Bearer ' + h.__token__)
    event_list = client.execute(h.__top8_query__, h.__top8_vars__)
    standings = j.loads(event_list)['data']['tournament']['events'][0]['standings']['nodes']

    cols = ["player", "standing", "autoqual"]
    top_df = p.DataFrame(columns=cols)
    for node in standings:
        if h.__top8_vars__['slug'] in h.__autoqual_slug__ and node['placement'] == 1:
            record = {"player": node['entrant']['name'], "standing": node['placement'], 'autoqual': 1}
            top_df = top_df.append(record, ignore_index=True)
        else:
            record = {"player": node['entrant']['name'], "standing": node['placement'], 'autoqual': 0}
            top_df = top_df.append(record, ignore_index=True)

    return top_df


def get_dqs() -> p.DataFrame:
    client = GraphQLClient('https://api.start.gg/gql/' + h.__APIversion__)
    client.inject_token('Bearer ' + h.__token__)
    record_count = 1
    cols = ['player']
    dqw_df = p.DataFrame(columns=cols)
    dql_df = p.DataFrame(columns=cols)

    while record_count != 0:
        set_list = client.execute(h.__dq_query__, h.__dq_vars__)

        sets = j.loads(set_list)
        count = j.loads(set_list)

        record_count = count['data']['tournament']['events'][0]['sets']['pageInfo']['total']
        sets = sets['data']['tournament']['events'][0]['sets']

        h.__dq_vars__['page'] += 1

        for node in sets['nodes']:
            if node['slots'][0]['standing']['stats']['score']['value'] == -1 \
                    and node['slots'][0]['standing']['placement'] == 2:
                if node['round'] > 0:
                    record = {'player': node['slots'][0]['standing']['entrant']['name']}
                    dqw_df = dqw_df.append(record, ignore_index=True)
                elif node['round'] < 0:
                    record = {'player': node['slots'][0]['standing']['entrant']['name']}
                    dql_df = dql_df.append(record, ignore_index=True)

            if node['slots'][1]['standing']['stats']['score']['value'] == -1 \
                    and node['slots'][1]['standing']['placement'] == 2:
                if node['round'] > 0:
                    record = {'player': node['slots'][1]['standing']['entrant']['name']}
                    dqw_df = dqw_df.append(record, ignore_index=True)
                elif node['round'] < 0:
                    record = {'player': node['slots'][1]['standing']['entrant']['name']}
                    dql_df = dql_df.append(record, ignore_index=True)

    dqw_df = dqw_df.drop_duplicates().sort_values(by=['player'])
    dql_df = dql_df.drop_duplicates().sort_values(by=['player'])
    dq_df = dqw_df.merge(dql_df, left_on='player', right_on='player')

    return dq_df


def mark_qualifiers(df: p.DataFrame) -> p.DataFrame:
    aq_df = df[df['autoqual'] == 1]
    sc_df = df[df['autoqual'] == 0].sort_values('score', ascending=False).head(8)
    nq_df = df[df['autoqual'] == 0].sort_values('score', ascending=False).tail(-8)
    aq_df['qualified'] = 1
    sc_df['qualified'] = 1
    df = p.concat([aq_df, sc_df, nq_df])

    with p.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000):
        time.sleep(1)
        print(aq_df)
        print(sc_df)
        print(nq_df)
        print('---------------------------')
        print(df.sort_values('rank', ascending=True))

    return df.sort_values('rank', ascending=True)


def calculate_scores() -> p.DataFrame:
    cols = ['player', 'score', 'rank', 'autoqual', 'qualified']
    the_list = p.DataFrame(columns=cols)
    for slug in zip(h.__tournament_slug__, h.__eventid__):
        # print(slug)
        h.__top8_vars__['slug'] = slug[0]
        h.__dq_vars__['slug'] = slug[0]
        h.__top8_vars__['eventID'] = slug[1]
        h.__dq_vars__['eventID'] = slug[1]
        h.__top8_vars__['page'] = 0
        h.__dq_vars__['page'] = 0

        # print(h.__top8_vars__)
        # print('---')
        # print(h.__dq_vars__)

        top8 = get_top_8()
        total = get_total_entrants()
        dq_count = len(get_dqs().index)
        entrants = total - dq_count

        # print('total - dq: ', entrants)
        # print('total: ', total)
        # print('dq: ', dq_count)

        for i, r in top8.iterrows():
            if r['player'] in the_list['player'].values:
                the_list['score'][the_list['player'] == r['player']] = the_list['score'][the_list['player'] == r['player']] + (score_map[r['standing']] + entrants)
                if the_list['autoqual'][the_list['player'] == r['player']].values == 0 \
                        and r['autoqual'] == 1:
                    the_list['autoqual'][the_list['player'] == r['player']] = 1
            else:
                record = {'player': r['player'],
                          'score': score_map[r['standing']] + entrants,
                          'rank': 0,
                          'autoqual': r['autoqual'],
                          'qualified': 0}
                the_list = the_list.append(record, ignore_index=True)

        the_list['rank'] = the_list['score'].rank(method='average', ascending=False)

        time.sleep(1)

    the_list = mark_qualifiers(the_list)
    return the_list
