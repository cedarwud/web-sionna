import axios from 'axios';

// 後端API的基礎URL - 根據環境動態設置
// 在開發模式下使用 localhost，在生產環境中使用真實 IP
const isLocalDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE_URL = isLocalDevelopment 
  ? 'http://localhost:8000/api/v1'
  : `http://${window.location.hostname}:8000/api/v1`;

// 設備類型枚舉（對應後端的 DeviceType）
export enum DeviceType {
  TRANSMITTER = 'transmitter',
  RECEIVER = 'receiver',
}

// 發射器類型枚舉
export enum TransmitterType {
  SIGNAL = 'signal',
  INTERFERER = 'interferer',
}

// 用於嵌套的發射器數據的介面
interface TransmitterData {
  transmitter_type: TransmitterType;
}

// 設備介面（對應後端的 Device schema）
export interface Device {
  id: number;
  name: string;
  x: number;
  y: number;
  z: number;
  active: boolean;
  device_type: DeviceType;
  transmitter: TransmitterData | null;
}

// 用於創建設備的介面
export interface DeviceCreate {
  name: string;
  x?: number;
  y?: number;
  z?: number;
  active?: boolean;
  device_type: DeviceType;
  transmitter_type?: TransmitterType;
}

// 用於更新設備的介面
export interface DeviceUpdate {
  name?: string;
  x?: number;
  y?: number;
  z?: number;
  active?: boolean;
  device_type?: DeviceType;
  transmitter_type?: TransmitterType;
}

// 獲取所有設備
export const getDevices = async (
  deviceType?: DeviceType,
  transmitterType?: TransmitterType
): Promise<Device[]> => {
  let url = `${API_BASE_URL}/devices/?limit=100`;
  
  if (deviceType) {
    url += `&device_type=${deviceType}`;
  }
  
  if (transmitterType) {
    url += `&transmitter_type=${transmitterType}`;
  }
  
  try {
    const response = await axios.get<Device[]>(url);
    return response.data;
  } catch (error) {
    console.error('獲取設備列表失敗:', error);
    throw error;
  }
};

// 根據ID獲取單個設備
export const getDeviceById = async (deviceId: number): Promise<Device> => {
  try {
    const response = await axios.get<Device>(`${API_BASE_URL}/devices/${deviceId}`);
    return response.data;
  } catch (error) {
    console.error(`獲取設備ID ${deviceId} 失敗:`, error);
    throw error;
  }
};

// 創建新設備
export const createDevice = async (deviceData: DeviceCreate): Promise<Device> => {
  try {
    // 如果是干擾器類型，使用專門的干擾器API
    if (deviceData.device_type === DeviceType.TRANSMITTER && 
        deviceData.transmitter_type === TransmitterType.INTERFERER) {
      console.log('使用干擾器專用API創建設備');
      // 轉換為後端期望的干擾器格式 - 包含device_type欄位
      const interfererData = {
        name: deviceData.name,
        x: deviceData.x ?? 0,
        y: deviceData.y ?? 0,
        z: deviceData.z ?? 0,
        active: deviceData.active !== undefined ? deviceData.active : true,
        device_type: DeviceType.TRANSMITTER  // 後端仍然需要此欄位
      };
      console.log('干擾器創建數據:', interfererData);
      const response = await axios.post<Device>(`${API_BASE_URL}/devices/interferer`, interfererData);
      return response.data;
    }
    
    // 一般設備創建
    console.log('使用標準API創建設備');
    const response = await axios.post<Device>(`${API_BASE_URL}/devices/`, deviceData);
    return response.data;
  } catch (error) {
    console.error('創建設備失敗:', error);
    throw error;
  }
};

// 更新現有設備
export const updateDevice = async (deviceId: number, deviceData: DeviceUpdate): Promise<Device> => {
  try {
    // 如果要更新為干擾器類型，使用專門的干擾器API
    if (deviceData.device_type === DeviceType.TRANSMITTER && 
        deviceData.transmitter_type === TransmitterType.INTERFERER) {
      console.log(`使用干擾器專用API更新設備 ID: ${deviceId}`);
      // 轉換為後端期望的干擾器格式 - 包含device_type字段
      const interfererData = {
        name: deviceData.name,
        x: deviceData.x,
        y: deviceData.y, 
        z: deviceData.z,
        active: deviceData.active,
        device_type: DeviceType.TRANSMITTER  // 保留device_type欄位
      };
      console.log('干擾器更新數據:', interfererData);
      const response = await axios.put<Device>(`${API_BASE_URL}/devices/interferer/${deviceId}`, interfererData);
      return response.data;
    }
    
    // 一般設備更新
    console.log(`使用標準API更新設備 ID: ${deviceId}`);
    const response = await axios.put<Device>(`${API_BASE_URL}/devices/${deviceId}`, deviceData);
    return response.data;
  } catch (error) {
    console.error(`更新設備ID ${deviceId} 失敗:`, error);
    throw error;
  }
};

// 刪除設備
export const deleteDevice = async (deviceId: number): Promise<void> => {
  try {
    await axios.delete(`${API_BASE_URL}/devices/${deviceId}`);
  } catch (error) {
    console.error(`刪除設備ID ${deviceId} 失敗:`, error);
    throw error;
  }
}; 