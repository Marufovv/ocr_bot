import pandas as pd
df=pd.read_csv('data.csv')
# print(df)
# df.info()
# df.isnull().sum()
# df.head()
# df.describe()
# print(df.describe())
# print(df.columns())
placed = (df["placement_status"](df["status"] == "1")).sum()
print("Ishga kirganlar soni:", placed)

not_placed = (df["placement_status"]  ).sum()
print("Ishga kirmaganlar soni:", not_placed)

total = len(df)
placement_percent = (placed / total) * 100
print("Ishga joylashish foizi:", placement_percent)





















