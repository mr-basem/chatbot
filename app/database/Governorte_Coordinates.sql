use kemet;
ALTER TABLE governorate
ADD COLUMN Latitude DECIMAL(10,6),
ADD COLUMN Longitude DECIMAL(10,6);

UPDATE governorate
SET
    Latitude = CASE GovernorateID
        WHEN 1 THEN 30.044420   -- Cairo
        WHEN 2 THEN 30.013056   -- Giza
        WHEN 3 THEN 31.200092   -- Alexandria
        WHEN 4 THEN 25.687243   -- Luxor
        WHEN 5 THEN 24.088938   -- Aswan
        WHEN 6 THEN 27.915817   -- South Sinai
        WHEN 7 THEN 30.312630   -- North Sinai
        WHEN 8 THEN 27.257896   -- Red Sea
        WHEN 9 THEN 31.354344   -- Matrouh
        WHEN 10 THEN 29.966834  -- Suez
        WHEN 11 THEN 30.596492  -- Ismailia
        WHEN 12 THEN 31.265289  -- Port Said
        WHEN 13 THEN 31.416481  -- Damietta
        WHEN 14 THEN 31.040949  -- Dakahlia
        WHEN 15 THEN 30.587681  -- Sharqia
        WHEN 16 THEN 30.179354  -- Qalyubia
        WHEN 17 THEN 30.875355  -- Gharbia
        WHEN 18 THEN 31.111656  -- Kafr el-Sheikh
        WHEN 19 THEN 30.597246  -- Monufia
        WHEN 20 THEN 30.848099  -- Beheira
        WHEN 21 THEN 29.308402  -- Fayoum
        WHEN 22 THEN 29.066127  -- Beni Suef
        WHEN 23 THEN 28.109884  -- Minya
        WHEN 24 THEN 27.180134  -- Asyut
        WHEN 25 THEN 26.556952  -- Sohag
        WHEN 26 THEN 26.155061  -- Qena
        WHEN 27 THEN 25.451462  -- New Valley
    END,

    Longitude = CASE GovernorateID
        WHEN 1 THEN 31.235712
        WHEN 2 THEN 31.208853
        WHEN 3 THEN 29.918739
        WHEN 4 THEN 32.639637
        WHEN 5 THEN 32.899830
        WHEN 6 THEN 34.329950
        WHEN 7 THEN 32.718140
        WHEN 8 THEN 33.811607
        WHEN 9 THEN 27.237316
        WHEN 10 THEN 32.549805
        WHEN 11 THEN 32.271458
        WHEN 12 THEN 32.301865
        WHEN 13 THEN 31.813316
        WHEN 14 THEN 31.378470
        WHEN 15 THEN 31.502010
        WHEN 16 THEN 31.205753
        WHEN 17 THEN 31.033510
        WHEN 18 THEN 30.939848
        WHEN 19 THEN 30.987633
        WHEN 20 THEN 30.343550
        WHEN 21 THEN 30.842850
        WHEN 22 THEN 31.099384
        WHEN 23 THEN 30.750305
        WHEN 24 THEN 31.183680
        WHEN 25 THEN 31.694780
        WHEN 26 THEN 32.716013
        WHEN 27 THEN 28.894168
    END;