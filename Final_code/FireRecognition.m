function score = FireRecognition(path)

% REQUIRE DEEP LEARNING TOOLBOX

net = alexnet ; 

% Read 
I = imread(path) ;

% Resize 
sz = net.Layers(1).InputSize ; 
I = imresize(I,[sz(1) sz(2)]) ; 

% Classify
label = classify(net,I)
[YPred,scores] = classify(net,I);

% Decide if fire is detected 
score = scores(981) ;
disp(score)
end