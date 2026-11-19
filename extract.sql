-- Run in AdventureWorks OLTP. The case uses the BOM effective on 23 June 2011.
DECLARE @AsOf date = '20110623';

WITH ActiveBOM AS (
    SELECT ProductAssemblyID, ComponentID, PerAssemblyQty
    FROM Production.BillOfMaterials
    WHERE StartDate <= @AsOf AND (EndDate IS NULL OR EndDate >= @AsOf)
)
SELECT d.SalesOrderID, d.SalesOrderDetailID, d.OrderQty, bike.ProductID,
       bike.Size AS BikeSize, frame.ProductNumber AS Frame,
       f.PerAssemblyQty AS FramesPerBike,
       seat.PerAssemblyQty * bolt.PerAssemblyQty AS SeatBoltsPerBike
FROM Sales.SalesOrderDetail AS d
JOIN Production.Product AS bike ON bike.ProductID = d.ProductID
JOIN ActiveBOM AS seat ON seat.ProductAssemblyID = bike.ProductID AND seat.ComponentID = 519
JOIN ActiveBOM AS bolt ON bolt.ProductAssemblyID = seat.ComponentID AND bolt.ComponentID = 497
JOIN ActiveBOM AS f ON f.ProductAssemblyID = bike.ProductID AND f.ComponentID IN (717,718,719)
JOIN Production.Product AS frame ON frame.ProductID = f.ComponentID
WHERE d.SalesOrderDetailID IN (372,374,375,425,454,456,457,458,1427)
ORDER BY d.SalesOrderID;
