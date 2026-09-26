export type GoupixDexSealedProductTileGainDirection = 'up' | 'down' | 'flat'

export type GoupixDexSealedProductTileGain = {
  amountLabel: string
  percentLabel: string | null
  direction: GoupixDexSealedProductTileGainDirection
}

export type GoupixDexSealedProductTileProps = {
  name: string
  imageUrl: string | null
  productType: string
  setName: string | null
  priceLabel: string | null
  purchaseLabel: string | null
  gain: GoupixDexSealedProductTileGain | null
  ownedQuantity: number
  isAddable: boolean
  isAdding: boolean
}
