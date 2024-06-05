from simlogging import mconsole, logging

def getDBs(client):
    response = client.query("show databases")
    try:
        dbs = [db[0] for db in response.raw['series'][0]['values']]
        return dbs
    except:
        mconsole("Could not parse influxdb database list: {}".format(response),level="ERROR")
    return None

def createDB(client,dbname):
    dbs = getDBs(client)
    if dbs is not None and len(dbs) > 0 and dbname in dbs:
        ''' Check openrtistdb influxdb '''
        mconsole("Database {} exists in influxdb".format(dbname))
        return True
    else:
        mconsole("Creating database {} in influxdb".format(dbname))
        client.create_database(dbname)
        client.alter_retention_policy("autogen", database=dbname, duration="30d", default=True)
        client.create_retention_policy('DefaultRetentionPolicy', '365d', "3", database = dbname, default=True)
        dbs = getDBs(client)
        if not dbname in dbs:
            mconsole("Could not create: {}".format(DBNAME),level="ERROR")
            return False
    return True