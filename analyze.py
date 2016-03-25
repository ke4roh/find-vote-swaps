#!/usr/bin/env python3
# Analyze votes as per http://madisonvoices.com/pdffiles/2008_2012_ElectionsResultsAnomaliesAndAnalysis_V1.5.pdf
# looking for votes swapped by tabulation machinery.
#
# The main data structure is a dictionary with keys representing choices and values a list of the numbers
# per precinct in nondecreasing size.  Various dict functions deal with this structure.
#
import operator
import sqlite3
import matplotlib.pyplot as plt

conn = sqlite3.connect(':memory:')
c = conn.cursor()


def main():
    import_votes()
    precinct_votes = get_precinct_votes()

    (county_cumulative_votes, county_cumulative_percentages) = tally_votes(precinct_votes)
    (deltas, county_anomalies) = rank_anomalies(county_cumulative_votes, county_cumulative_percentages)
    report_anomalies(deltas, county_cumulative_votes, county_cumulative_percentages, county_anomalies)


def import_votes():
    """
    Put votes into the in-memory database.  This is exactly the format from NC board of elections, but
    it needs only to have the county name, precinct, contest name, choice, and total_votes.  Those fields
    are fundamental to operation, and the rest are imported because they were there.
    """
    c.execute("""CREATE TABLE IF NOT EXISTS v
         (County TEXT, Election_Date TEXT, Precinct TEXT,
          Contest_Group_ID INTEGER, Contest_Type TEXT,
          Contest_Name TEXT, Choice TEXT, Choice_Party TEXT,
          Vote_For INTEGER,	Election_Day INTEGER, One_Stop INTEGER,
          Absentee_by_Mail INTEGER, Provisional INTEGER,
          Total_Votes INTEGER);
    """)
    c.execute("CREATE INDEX cocop ON v(Contest_Name, County, Precinct)")

    filename = 'resultsPCT20160315.txt'
    # filename = 'rwakepres.txt'
    with open(filename) as f:
        votes = f.readlines()

    for v in votes[1:]:
        c.execute('INSERT INTO v values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', v.rstrip().split('\t', 13))


def get_precinct_votes():
    """
    Look in the DB and return all the votes in nondecreasing order by precinct.
    :return:
    """
    c.execute(
        "SELECT Contest_Name, County, Precinct, Sum(Total_Votes) as Votes from v group by County, Precinct, Contest_Name order by Votes ASC")
    return c.fetchall()


def tally_votes(precinct_votes):
    """
    Count up the cumulative votes.
    :param precinct_votes: a list of precincts and their contests in order by how many votes there were.
    :return: a tuple with the cumulative votes and percentages found
    """
    county_cumulative_votes = {}
    county_cumulative_percentages = {}
    for pv in precinct_votes:
        c.execute(
            "SELECT Choice, Total_Votes from v where Contest_Name=? and County=? and Precinct=? order by Choice ASC",
            pv[0:3])
        precinct_choices = {}
        for pc in c.fetchall():
            precinct_choices[pc[0]] = pc[1]
        if pv[0:2] not in county_cumulative_votes:
            county_cumulative_votes[pv[0:2]] = {}
            county_cumulative_percentages[pv[0:2]] = {}
            cumulative_choices = precinct_choices
        else:
            cumulative_choices = {}
            for choice, vote in precinct_choices.items():
                cumulative_choices[choice] = vote + county_cumulative_votes[pv[0:2]][choice][-1]
        append_map_array(county_cumulative_votes[pv[0:2]], cumulative_choices)
        append_map_array(county_cumulative_percentages[pv[0:2]], normalize(cumulative_choices))

    return (county_cumulative_votes, county_cumulative_percentages)


def normalize(cv):
    """
    :param cv: A map containing integer values
    :return: A copy of that map with same keys and float values, normalized
    """
    pct = {}
    cvsum = sum(cv.values())
    for k, v in cv.items():
        if cvsum == 0:
            x = 0
        else:
            x = v * 1.0 / cvsum
        pct[k] = x
    return pct


def append_map_array(ma, cv):
    for k in cv.keys():
        if k in ma:
            ma[k].append(cv[k])
        else:
            ma[k] = [cv[k]]


def slice_dict(d, min, max=None):
    d2 = {}
    for k, v in d.items():
        if max:
            d2[k] = v[min:max]
        else:
            d2[k] = v[min]
    return d2


def dict_len(d):
    for v in d.values():
        return len(v)


def dict_median(p):
    """
    :param p: a dictionary of lists of votes for candidates
    :return: a dictionary conaining only the median value for each candidate
    """
    m = {}
    for k, v in p.items():
        l = sorted(v)
        m[k] = l[int(len(l) / 2)]
    return m


def dict_list_ix(d, numtofind, min=0, max=None):
    """
     This effectively constructs a list of all the sums of votes for each precinct and returns
     the index of the first precinct at which there had accumulated at least numtofind votes.
    """
    if max is None:
        return dict_list_ix(d, numtofind, min, dict_len(d))
    check_ix = int((min + max) / 2)
    here_val = sum(slice_dict(d, check_ix).values())
    if here_val > numtofind:
        return dict_list_ix(d, numtofind, min, check_ix)
    elif here_val < numtofind and min < max - 1:
        return dict_list_ix(d, numtofind, check_ix, max)
    else:
        return check_ix


def rank_anomalies(county_cumulative_votes, county_cumulative_percentages):
    deltas = {}
    county_anomalies = {}
    for co, percentages in county_cumulative_percentages.items():
        precinct_count = None
        # Make sure every choice was available in every precinct
        for choice, votes in percentages.items():
            if precinct_count is None:
                precinct_count = len(votes)
            else:
                assert precinct_count == len(votes)

        total_votes = sum(slice_dict(county_cumulative_votes[co], -1).values())
        if precinct_count > 15 and total_votes > 1000:
            reference = dict_median(
                slice_dict(percentages, dict_list_ix(county_cumulative_votes[co], total_votes / 20),
                           dict_list_ix(county_cumulative_votes[co], total_votes / 5)))
            final = slice_dict(percentages, -1)
            delta = 0
            county_anomalies[co] = {}
            for c in reference.keys():
                county_anomalies[co][c] = final[c] - reference[c]
                delta += abs(county_anomalies[co][c])
            if delta > .04:
                deltas[co] = round(delta, 3)
    deltas = sorted(deltas.items(), key=operator.itemgetter(1), reverse=True)
    return (deltas, county_anomalies)


def short_name(choice):
    if choice == "No Preference":
        return "Nobody"
    else:
        return choice.rsplit(' ', 1)[-1]


def generate_chart(co, ccv, pct, anomaly):
    # Sum up the votes for all candidates into x
    x = None
    for c, vv in ccv.items():
        if x is None:
            x = vv[:]
        else:
            for i in range(0, len(vv)):
                x[i] += vv[i]

    for choice, votes in pct.items():
        if abs(anomaly[choice]) < .01:
            small = "_"
        else:
            small = ""
        plt.plot(x, [100 * x for x in pct[choice]], 'o-',
                 label="%s%s %+d%%" % (small, short_name(choice), int(anomaly[choice] * 100 + 0.5)))
    plt.axis([0, x[-1], 0, None])
    plt.title(co[0] + " " + co[1])
    plt.ylabel("% of vote")
    plt.xlabel("cumulative vote tally")
    plt.legend(loc='best')
    # plt.show()
    plt.savefig((co[0] + '-' + co[1]).replace(' ', '_').replace('(', '').replace(')', ''))
    plt.close()


def report_anomalies(deltas, county_cumulative_votes, county_cumulative_percentages, county_anomalies):
    for co, delta in deltas:
        oddest = sorted(county_anomalies[co].items(), key=operator.itemgetter(1), reverse=True)
        print("%s Δ%.3f %s %+d (%d votes)" % (co, delta, short_name(oddest[0][0]),
                                     int(100 * oddest[0][1] + 0.5),
                                     sum(slice_dict(county_cumulative_votes[co], -1).values())))
    # print('\n'.join([str(x) for x in deltas]))
    # For the top few, graph it
    for dd in deltas[0:25]:
        generate_chart(dd[0],
                       county_cumulative_votes[dd[0]],
                       county_cumulative_percentages[dd[0]],
                       county_anomalies[dd[0]])


main()
