package org.trustedanalytics.sparktk.frame.internal.ops.matrix

import org.apache.spark.rdd.RDD
import org.apache.spark.sql.catalyst.expressions.GenericRow
import org.apache.spark.sql.Row
import org.apache.spark.mllib.linalg.{ DenseMatrix => DM }
import breeze.linalg.{ DenseMatrix => BDM }
import org.trustedanalytics.sparktk.frame.{ Column, DataTypes }
import org.trustedanalytics.sparktk.frame.internal.{ BaseFrame, FrameState, FrameTransform, VectorFunctions }
import org.trustedanalytics.sparktk.frame.internal.rdd.FrameRdd

trait SVDTransform extends BaseFrame {

  def svd(matrixColumnName: String): Unit = {
    execute(SVD(matrixColumnName))
  }
}

case class SVD(matrixColumnName: String) extends FrameTransform {

  require(matrixColumnName != null, "Matrix column name cannot be null")

  override def work(state: FrameState): FrameState = {
    // run the operation
    val svdRdd = SVD.svd(state, matrixColumnName)

    // save results
    val updatedSchema = state.schema.addColumns(Seq(Column("U", DataTypes.matrix), Column("V", DataTypes.matrix), Column("singular_values", DataTypes.vector(svdRdd._2))))

    FrameState(svdRdd._1, updatedSchema)
  }
}

object SVD extends Serializable {
  /**
   * Computes the svd for each matrix of the frame
   *
   *
   */
  def svd(frameRdd: FrameRdd, matrixColumnName: String): (RDD[Row], Int) = {
    frameRdd.schema.requireColumnIsType(matrixColumnName, DataTypes.matrix)
    var singularValuesSize = 0
    (frameRdd.mapRows(row => {
      val matrix = row.value(matrixColumnName).asInstanceOf[DM]
      val breezeMatrix = new BDM(matrix.numRows, matrix.numCols, matrix.toArray)
      val svdResult = breeze.linalg.svd(breezeMatrix)
      val newColumns = (svdResult.U, svdResult.Vt, svdResult.singularValues)
      singularValuesSize = svdResult.singularValues.size
      new GenericRow(row.valuesAsArray() :+ newColumns)
    }), singularValuesSize)
  }

}