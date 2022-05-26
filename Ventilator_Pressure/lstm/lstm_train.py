import numpy as np
import pandas as pd
import torch
from model import *
train_path = "./input/train.csv"
test_path = "./input/test.csv"
sample_sub = "./input/sample_submission.csv"

train_data = pd.read_csv(train_path)
test_data = pd.read_csv(test_path) 
sample_data = pd.read_csv(sample_sub) 

# id,breath_id,R,C,time_step,u_in,u_out,pressure
# print(train_data.describe())

def change_columns(value, data):
    change_columns = pd.get_dummies(data[f'{value}'])
    if value == 'C':
        change_columns.rename(columns = {10:f'{value}_10',
                                        20:f'{value}_20',
                                        50:f'{value}_50'}, inplace=True)
    elif value =='R':
        change_columns.rename(columns = {5:f'{value}_5',
                                        20:f'{value}_20',
                                        50:f'{value}_50'}, inplace=True)
    return change_columns

change_columns_C = change_columns('C', train_data)
change_columns_R = change_columns('R', train_data)

train_label_data = train_data['pressure']

train_data = pd.concat([train_data,change_columns_C,change_columns_R],axis=1)
train_data = train_data.drop(['id','breath_id','pressure','R','C','R_5','C_10'], axis=1)

# 데이터 총개수의 95% => 5734200개     5%는 test_dataset으로 사용하겠음
test_data = train_data.iloc[:800]
train_data = train_data.iloc[800:8800]

test_label_data = train_label_data.iloc[:800]
train_label_data = train_label_data.iloc[800:8800]

def numpy_to_tensor(variable):
    x = variable.values
    x = np.array(x, dtype=np.float32)
    x = torch.from_numpy(x)
    return x

train_data = numpy_to_tensor(train_data).unsqueeze(1)
test_data = numpy_to_tensor(test_data).unsqueeze(1)
train_label_data = numpy_to_tensor(train_label_data)
test_label_data = numpy_to_tensor(test_label_data)

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")  # device

class LSTM1(nn.Module):
  def __init__(self, num_classes, input_size, hidden_size, num_layers):
    super(LSTM1, self).__init__()
    self.num_classes = num_classes #number of classes
    self.num_layers = num_layers #number of layers
    self.input_size = input_size #input size
    self.hidden_size = hidden_size #hidden state
 
    self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size,
                      num_layers=num_layers, batch_first=True, bidirectional=True) #lstm
    self.fc_1 =  nn.Linear(hidden_size, 512) #fully connected 1
    self.fc_2 =  nn.Linear(512, 512)
    
    self.pressure_in = nn.Linear(512, num_classes) #fully connected last layer
    self.pressure_out = nn.Linear(512, num_classes)
    
    self.relu = nn.ReLU() 

  def forward(self,x):
    h_0 = torch.zeros(self.num_layers*2, x.size(0), self.hidden_size).to(device) #hidden state
    c_0 = torch.zeros(self.num_layers*2, x.size(0), self.hidden_size).to(device) #internal state   
    output, (hn, cn) = self.lstm(x, (h_0, c_0)) #lstm with input, hidden, and internal state
    # 실제로는 h_0, c_0 필요없음 torch에서 자동생성
    
    # cn.shape == torch.Size([1, 4500, 2])
    hn = hn.squeeze(0) #reshaping the data for Dense layer next
    # hn.shape == torch.Size([4500, 2])
    out = self.relu(hn)
    out = self.fc_1(out) #first Dense
    # out.shape == torch.Size([4500, 128])
    out = self.relu(out)
    out = self.fc_2(out)
    out = self.relu(out) #relu
    pressure_in = self.pressure_in(out) #Final Output
    # pressure_in.shape == torch.Size([4500, 1])
    pressure_out = self.pressure_out(out)

    return pressure_in, pressure_out

num_epochs = 1000 #1000 epochs
learning_rate = 0.001 #0.001 lr

input_size = 11 #number of features
hidden_size = 512 #number of features in hidden state
num_layers = 1 #number of stacked lstm layers

num_classes = 1 #number of output classes 
lstm1 = LSTM1(num_classes, input_size, hidden_size, num_layers).to(device)
loss_function = torch.nn.L1Loss()    # mean-squared error for regression
optimizer = torch.optim.Adam(lstm1.parameters(), lr=learning_rate)  # adam optimizer

batch_size = 80
batch_num_train = len(train_data) // batch_size
batch_num_test = len(test_data) // batch_size

for epoch in range(num_epochs):
    running_loss = 0
    for i in range(batch_num_train):
        start = i * batch_size
        end = start + batch_size

        pressure_in, pressure_out = lstm1.forward(train_data[start:end].to(device)) #forward pass
        
        pressure_in = (pressure_in[0][:][:] + pressure_in[1][:][2])/2
        pressure_in = pressure_in.squeeze(1)
        optimizer.zero_grad() #caluclate the gradient, manually setting to 0
        
        # print(pressure_in.squeeze(1).shape)
        # print(train_label_data[start:end].shape)

        # obtain the loss function
        loss = loss_function(pressure_in, train_label_data[start:end][:].to(device))

        # print(pressure_in.shape)
        

        loss.backward() #calculates the loss of the loss function

        optimizer.step() #improve from loss, i.e backprop
        running_loss += loss.item()

        if i == 0:
            # print("학습을 시작합니다.")
            pass
        elif i % 50 == 0:
            print(f'loss : {running_loss/50}')
        
    if epoch % 1 == 0:
        print("")
        print(f"epochs:{epoch}")
        print("")

PATH = './weights/'
torch.save(lstm1.state_dict(), PATH+'model_LSTM.pt')


# 1.45 나왔음 1000 epochs에 이건 얼마나 나오는지 볼것..!

# 1.46... 별로변화없음...